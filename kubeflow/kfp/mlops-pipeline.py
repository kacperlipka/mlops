from kfp import dsl
from kfp import kubernetes
import kfp.compiler as compiler
import json

@dsl.component(base_image="python:3.10", packages_to_install=["pandas", "numpy", "pathlib"])
def prepare_data(hours_back: int = 3):
    """Prepare time series data for training"""
    import pandas as pd
    from datetime import datetime, timedelta
    from pathlib import Path

    path = Path("/data/metrics.csv")
    df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
    df = df.resample("1min").mean().ffill()

    cutoff_time = df.index.max() - timedelta(hours=hours_back)
    df_filtered = df[df.index > cutoff_time]
    df_filtered = df_filtered.dropna()
    
    df_filtered.to_csv("/data/data.csv")


@dsl.component(
    base_image="python:3.10",
    packages_to_install=["tensorflow", "numpy", "pandas", "model_registry", "scikit-learn", "pathlib"],
)
def train_model(model_name: str, model_version: str, author: str, model_pvc: str):
    """Train LSTM model for time series forecasting"""
    import tensorflow as tf
    import numpy as np
    import pandas as pd
    import os
    from model_registry import ModelRegistry
    from pathlib import Path
    
    path = Path("/data/data.csv")
    df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
    
    input_sequence_length = 60
    output_sequence_length = 60
    
    X, y = [], []
    for i in range(len(df) - (input_sequence_length + output_sequence_length)):
        X.append(df[i:i + input_sequence_length])
        y.append(df[i + input_sequence_length:i + input_sequence_length + output_sequence_length])

    X, y = np.array(X), np.array(y)
    
    train_size = int(0.8 * len(X))
    X_train, X_test = X[:train_size], X[train_size:]
    y_train, y_test = y[:train_size], y[train_size:]
    
    train_dataset = tf.data.Dataset.from_tensor_slices((X_train, y_train)).batch(32)
    test_dataset = tf.data.Dataset.from_tensor_slices((X_test, y_test)).batch(32)
    
    model = tf.keras.models.Sequential([
        tf.keras.layers.LSTM(64, input_shape=(60, 1), return_sequences=True),
        tf.keras.layers.LSTM(64, return_sequences=False),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(60)
    ])
    
    model.compile(
        optimizer='adam',
        loss='mse',
        metrics=['mae']
    )
    
    history = model.fit(train_dataset, epochs=50)
    
    # Create versioned directory structure
    model_dir = f'/models/{model_name}'
    version_dir = os.path.join(model_dir, model_version)
    os.makedirs(version_dir, exist_ok=True)
    
    # Save model
    model.export(version_dir)
    
    # Register model
    registry = ModelRegistry(
        server_address="http://model-registry-service.kubeflow.svc.cluster.local",
        port=8080,
        author=author,
        is_secure=False
    )
    
    registered_model = registry.register_model(
        model_name,
        f"pvc://{model_pvc}/{model_name}/{model_version}",
        model_format_name="tensorflow",
        model_format_version="2.0",
        version=model_version,
        description="Simple RNN model for CPU usage prediction",
        metadata={
            "loss": float(history.history['loss'][-1]),
            "mae": float(history.history['mae'][-1])
        }
    )

@dsl.component(
    base_image="python:3.10", packages_to_install=["kserve", "model_registry"]
)
def deploy_model(model_name: str, namespace: str, model_pvc: str):
    """Deploy model to KServe with rolling updates"""
    from kubernetes import client
    from kserve import KServeClient, constants
    from model_registry import ModelRegistry
    from kserve import V1beta1InferenceService
    from kserve import V1beta1InferenceServiceSpec
    from kserve import V1beta1PredictorSpec
    from kserve import V1beta1TFServingSpec

    kserve_client = KServeClient()

    isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND,
        metadata=client.V1ObjectMeta(
            name=model_name,
            namespace=namespace,
        ),
        spec=V1beta1InferenceServiceSpec(
            predictor=V1beta1PredictorSpec(
                tensorflow=V1beta1TFServingSpec(
                    storage_uri=f"pvc://{model_pvc}/{model_name}",
                    args=["--model_base_path=/mnt/pvc/cpu-usage-forecaster"]
                )
            )
        )
    )

    try:
        kserve_client.get(model_name, isvc)
    except:
        kserve_client.create(isvc, watch=True)


@dsl.pipeline(name="Time Series Forecasting Pipeline")
def forecasting_pipeline(
    hours_back: int = 10,
    data_pvc: str = "metrics-data-pvc",
    model_pvc: str = "metrics-data-pvc",
    model_name: str = "cpu-usage-forecaster",
    model_version: str = "1",
    author: str = "system",
    namespace: str = "kubeflow-user-example-com"
):
    # Prepare data
    prepare_step = prepare_data(hours_back=hours_back)
    prepare_step.set_caching_options(False)
    kubernetes.mount_pvc(prepare_step, pvc_name=data_pvc, mount_path="/data")

    # Train model
    train_step = train_model(
        model_name=model_name, model_version=model_version, author=author, model_pvc=model_pvc
    )
    kubernetes.mount_pvc(train_step, pvc_name=model_pvc, mount_path="/models")
    kubernetes.mount_pvc(train_step, pvc_name=data_pvc, mount_path="/data")
    
    # Deploy model
    deploy_step = deploy_model(
        model_name=model_name, namespace=namespace, model_pvc=model_pvc
    )

    # Define execution order
    train_step.after(prepare_step)
    deploy_step.after(train_step)


if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=forecasting_pipeline, package_path="forecasting_pipeline.yaml"
    )