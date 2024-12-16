from flask import Flask, request, jsonify
import logging
from datetime import datetime
import json

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for maximum visibility
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_alert():
    try:
        # Log everything we can about the request
        logger.debug("=== New Webhook Request ===")
        logger.debug(f"Request Method: {request.method}")
        logger.debug(f"Endpoint: {request.endpoint}")
        logger.debug("=== Headers ===")
        for header, value in request.headers:
            logger.debug(f"{header}: {value}")
        
        logger.debug("=== Request Data ===")
        raw_data = request.get_data(as_text=True)
        logger.debug(f"Raw data: {raw_data}")
        
        # Try to parse JSON if present
        if request.is_json:
            data = request.json
            logger.debug(f"JSON data: {json.dumps(data, indent=2)}")

        return jsonify({
            "status": "success",
            "message": "Webhook received successfully",
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    logger.info("Starting debug webhook server on port 5000...")
    app.run(host='0.0.0.0', port=5000)