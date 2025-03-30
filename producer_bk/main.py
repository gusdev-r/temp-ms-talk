import os
import json
import logging
from flask import Flask, request, jsonify
from services.service import SendFormQuestionService


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

send_form_service = SendFormQuestionService()

fake_form_question_data = os.path.join(os.path.dirname(__file__), "fake_data.json")

app = Flask(__name__)


@app.route("/producer", methods=["GET"])
def hello_world():
    """Endpoint for api test"""
    return jsonify(
        {
            "status": "success",
            "message": "Yes, it's working!",
        }
    )


@app.route("/submit_form_question", methods=["POST"])
def handle_form_question():
    try:
        with open(fake_form_question_data, "r") as file:
            data = json.load(file)
            logger.info(f"Loaded fake data: {data}")
        success = send_form_service.send_to_rabbitmq(data)

        if success:
            logger.info("Successfully queued fake data")
            return jsonify(
                {
                    "status": "success",
                    "message": "Form data queued",
                    "data": data,
                }
            )
        else:
            logger.error("Failed to queue fake data")
            return (
                jsonify({"status": "error", "message": "Failed to queue form data"}),
                500,
            )

    except FileNotFoundError:
        logger.error(f"Fake data file not found at {fake_form_question_data}")
        return jsonify({"status": "error", "message": "Fake data file not found"}), 500
    except json.JSONDecodeError:
        logger.error("Invalid JSON in fake data file")
        return jsonify({"status": "error", "message": "Invalid fake data format"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@app.teardown_appcontext
def cleanup(exception=None):
    """Clean up resources when app shuts down"""
    send_form_service.close()
    logger.info("Service cleanup completed")


if __name__ == "__main__":
    logger.info("Starting producer service on port 5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
