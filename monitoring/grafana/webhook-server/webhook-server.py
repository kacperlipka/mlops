from flask import Flask, request, jsonify
import logging
from datetime import datetime
import json
import kfp
from model_registry import ModelRegistry

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_model_registry():
    """Initialize Model Registry client with proper configuration."""
    try:
        registry = ModelRegistry(
            server_address="http://model-registry-service.kubeflow.svc.cluster.local",
            port=8080,
            author="system",
            is_secure=False
        )
        logger.info("Successfully initialized Model Registry client")
        return registry
    except Exception as e:
        logger.error(f"Error initializing Model Registry client: {str(e)}")
        raise

def get_latest_model_version(registry, model_name):
    """Get the latest model version safely."""
    try:
        versions = registry.get_model_versions(model_name)
        if not versions:
            logger.info(f"No versions found for model {model_name}, starting from version 1")
            return 0
        latest_version = max(int(version.name) for version in versions)
        logger.info(f"Found latest version {latest_version} for model {model_name}")
        return latest_version
    except Exception as e:
        logger.error(f"Error getting latest model version: {str(e)}")
        raise

@app.route('/webhook', methods=['POST'])
def handle_alert():
    try:
        # Log request details
        logger.debug("=== New Webhook Request ===")
        logger.debug(f"Request Method: {request.method}")
        logger.debug(f"Endpoint: {request.endpoint}")
        logger.debug("=== Headers ===")
        for header, value in request.headers:
            logger.debug(f"{header}: {value}")
        
        logger.debug("=== Request Data ===")
        raw_data = request.get_data(as_text=True)
        logger.debug(f"Raw data: {raw_data}")
        
        if request.is_json:
            alert_data = request.json
            logger.debug(f"JSON data: {json.dumps(alert_data, indent=2)}")
            
            # Initialize Model Registry
            registry = get_model_registry()
            
            # Initialize KFP client
            logger.info("Initializing KFP client")
            client = kfp.Client()
            client.set_user_namespace(namespace="kubeflow-user-example-com")
            
            # Get experiment ID
            try:
                experiment = client.get_experiment(experiment_name="mlops")
                experiment_id = experiment.experiment_id
                logger.info(f"Found experiment ID: {experiment_id}")
            except Exception as e:
                logger.error(f"Error getting experiment: {str(e)}")
                raise
            
            # Get pipeline and version IDs
            try:
                pipelines = client.list_pipelines(namespace="kubeflow-user-example-com").pipelines
                if not pipelines:
                    raise ValueError("No pipelines found in namespace")
                pipeline_id = pipelines[0].pipeline_id
                
                versions = client.list_pipeline_versions(pipeline_id=pipeline_id).pipeline_versions
                if not versions:
                    raise ValueError(f"No versions found for pipeline {pipeline_id}")
                version_id = versions[-1].pipeline_version_id
                
                logger.info(f"Using pipeline ID: {pipeline_id}, version ID: {version_id}")
            except Exception as e:
                logger.error(f"Error getting pipeline/version info: {str(e)}")
                raise
            
            # Generate job name
            job_name = f"grafana-alert-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            # Get next model version
            model_version = get_latest_model_version(registry, "cpu-usage-forecaster") + 1
            logger.info(f"Using model version: {model_version}")

            # Prepare pipeline parameters
            params = {
                'hours_back': 8,
                'model_version': f"{model_version}"
            }

            # Run the pipeline with detailed configuration
            logger.info("Starting pipeline run")
            run = client.run_pipeline(
                experiment_id=experiment_id,
                pipeline_id=pipeline_id,
                version_id=version_id,
                job_name=job_name,
                params=params
            )
            
            logger.info(f"Successfully started pipeline run with ID: {run.run_id}")
            
            return jsonify({
                "status": "success",
                "message": "Pipeline run started successfully",
                "timestamp": datetime.now().isoformat(),
                "run_id": run.run_id,
                "job_name": job_name,
                "experiment_id": experiment_id,
                "model_version": model_version
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
    logger.info("Starting KFP webhook server on port 5000...")
    app.run(host='0.0.0.0', port=5000)