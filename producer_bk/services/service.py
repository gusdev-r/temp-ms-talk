import pika
import json
import os
import logging
from typing import Optional
from pika.adapters.blocking_connection import BlockingChannel


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SendFormQuestionService:
    def __init__(self):
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None
        self.max_connection_attempts = 3
        self.retry_delay = 5

    def _get_connection_parameters(self) -> pika.ConnectionParameters:
        """Create RabbitMQ connection parameters with environment variables"""
        return pika.ConnectionParameters(
            host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
            port=int(os.getenv("RABBITMQ_PORT", "5672")),
            credentials=pika.PlainCredentials(
                username=os.getenv("RABBITMQ_USER", "user"),
                password=os.getenv("RABBITMQ_PASSWORD", "password"),
            ),
            heartbeat=600,
            blocked_connection_timeout=300,
            connection_attempts=self.max_connection_attempts,
            retry_delay=self.retry_delay,
        )

    def _connect(self) -> bool:
        """Establish connection to RabbitMQ"""
        try:
            self.connection = pika.BlockingConnection(self._get_connection_parameters())
            self.channel = self.connection.channel()
            self._setup_queue()
            return True
        except pika.exceptions.AMQPError as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            return False

    def _setup_queue(self):
        """Declare the queue with DLX settings"""
        self.channel.queue_declare(
            queue="form_submissions",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "dlx_exchange",
                "x-message-ttl": 86400000,
            },
        )

    def _ensure_connection(self) -> bool:
        """Ensure we have an active connection"""
        if self.connection and self.connection.is_open:
            return True

        return self._connect()

    def send_to_rabbitmq(self, form_data: dict) -> bool:
        """Send form data to RabbitMQ queue"""
        try:
            if not self._ensure_connection():
                logger.error("Could not establish RabbitMQ connection")
                return False

            self.channel.basic_publish(
                exchange="",
                routing_key="form_submissions",
                body=json.dumps(form_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type="application/json",
                ),
            )
            logger.info("Successfully sent message to RabbitMQ")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Failed to serialize form data: {e}")
            return False
        except pika.exceptions.AMQPError as e:
            logger.error(f"RabbitMQ error while sending message: {e}")

            if self.connection and self.connection.is_open:
                self.connection.close()
            return False
        except Exception as e:
            logger.error(f"Unexpected error while sending message: {e}")
            return False

    def close(self):
        """Clean up connections"""
        if self.connection and self.connection.is_open:
            self.connection.close()
            logger.info("RabbitMQ connection closed")


rabbitmq_producer = SendFormQuestionService()
