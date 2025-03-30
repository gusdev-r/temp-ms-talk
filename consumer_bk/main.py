from flask import Flask, jsonify
import logging
import threading
from config.rabbimq import RabbitMQConsumer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/consumer", methods=["GET"])
def hello_world():
    """Endpoint for api test"""
    return jsonify(
        {
            "status": "success",
            "message": "Yes, it's working!",
        }
    )


@app.route("/health")
def health_check():
    """Endpoint for health checks"""
    return {"status": "healthy"}, 200


def start_consumer():
    """Start the RabbitMQ consumer in a separate thread"""
    try:
        consumer = RabbitMQConsumer()
        logger.info("Starting RabbitMQ consumer...")
        consumer.start()
    except Exception as e:
        logger.error(f"Failed to start consumer: {e}")


if __name__ == "__main__":

    consumer_thread = threading.Thread(target=start_consumer, daemon=True)
    consumer_thread.start()

    logger.info("Starting consumer service on port 5002")
    app.run(host="0.0.0.0", port=5002)
