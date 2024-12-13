from flask import Flask, request, jsonify
import logging
from datetime import datetime
import kfp
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_alert():
    try:
        # Detailed logging of the incoming request
        logger.info("=== Webhook Request Details ===")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Raw Data: {request.get_data(as_text=True)}")
        
        alert_data = request.json
        logger.info(f"Parsed JSON: {json.dumps(alert_data, indent=2)}")

        # Initialize KFP client
        logger.info("Initializing KFP client...")
        kfp_client = kfp.Client()
        
        # Create pipeline run
        logger.info("Starting pipeline run...")
        run = kfp_client.create_run_from_pipeline_package(
            pipeline_file="/mlops/forecasting_pipeline.yaml"
        )
        
        logger.info(f"Successfully started pipeline run with ID: {run.run_id}")
        
        return jsonify({
            "status": "success",
            "message": "Pipeline run started",
            "run_id": run.run_id
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
    logger.info("Starting Grafana webhook server on port 5000...")
    app.run(host='0.0.0.0', port=5000)