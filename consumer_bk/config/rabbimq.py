import pika
import pika.exceptions
import json
import time
import os
import logging
from typing import Optional
from services.service import ProcessFormQuestionService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    def __init__(self):
        self.process_service = ProcessFormQuestionService()
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self.max_retries = 3
        self.retry_delay = 5

    def _get_connection_parameters(self) -> pika.ConnectionParameters:
        return pika.ConnectionParameters(
            host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
            port=int(os.getenv("RABBITMQ_PORT", "5672")),
            credentials=pika.PlainCredentials(
                username=os.getenv("RABBITMQ_USER", "user"),
                password=os.getenv("RABBITMQ_PASSWORD", "password"),
            ),
            heartbeat=600,
            blocked_connection_timeout=300,
            connection_attempts=3,
            retry_delay=self.retry_delay,
        )

    def _connect(self) -> bool:
        """Establish connection to RabbitMQ"""
        try:
            self.connection = pika.BlockingConnection(self._get_connection_parameters())
            self.channel = self.connection.channel()
            self._setup_queues()
            return True
        except pika.exceptions.AMQPError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False

    def _setup_queues(self):
        """Declare queues and exchanges"""
        self.channel.queue_declare(
            queue="form_submissions",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx_exchange",
                "x-message-ttl": 86400000,
            },
        )

        self.channel.exchange_declare(
            exchange="dlx_exchange", exchange_type="direct", durable=True
        )

        self.channel.queue_declare(queue="dead_letter_queue", durable=True)

        self.channel.queue_bind(
            exchange="dlx_exchange",
            queue="dead_letter_queue",
            routing_key="form_submissions",
        )

    def _process_message(self, body: bytes) -> bool:
        """Process the message using your service"""
        try:
            data = json.loads(body)
            logger.info(f"Processing message: {data}")
            return self.process_service.process_logic(data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return False

    def _message_callback(self, ch, method, properties, body):
        """Callback for handling incoming messages"""
        try:
            if self._process_message(body):
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info("Message processed successfully")
            else:
                retry_count = (
                    properties.headers.get("x-retry-count", 0)
                    if properties.headers
                    else 0
                )

                if retry_count < self.max_retries:
                    headers = properties.headers or {}
                    headers["x-retry-count"] = retry_count + 1

                    ch.basic_publish(
                        exchange="",
                        routing_key="form_submissions",
                        body=body,
                        properties=pika.BasicProperties(
                            delivery_mode=2, headers=headers
                        ),
                    )
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    logger.warning(f"Message requeued for retry {retry_count + 1}")
                else:
                    ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
                    logger.error("Max retries reached, message rejected")
        except Exception as e:
            logger.error(f"Error in message callback: {e}")
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)

    def start(self):
        """Start consuming messages"""
        while True:
            try:
                if not self._connect():
                    time.sleep(self.retry_delay)
                    continue

                logger.info("Connected to RabbitMQ")

                self.channel.basic_qos(prefetch_count=1)

                self.channel.basic_consume(
                    queue="form_submissions",
                    on_message_callback=self._message_callback,
                    auto_ack=False,
                )

                logger.info("Consumer ready. Waiting for messages...")
                self.channel.start_consuming()

            except pika.exceptions.AMQPError as e:
                logger.error(f"RabbitMQ connection error: {e}")
                if self.connection and self.connection.is_open:
                    self.connection.close()
                time.sleep(self.retry_delay)

            except KeyboardInterrupt:
                logger.info("Consumer stopped by user")
                if self.connection and self.connection.is_open:
                    self.connection.close()
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(self.retry_delay)
