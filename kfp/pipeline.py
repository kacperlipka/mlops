from kfp import dsl
from kfp import kubernetes
import kfp.compiler as compiler
import json

@dsl.component(base_image="python:3.10", packages_to_install=["pandas", "numpy"])
def prepare_data(hours_back: int = 24):
    """Prepare time series data for training"""
    import pandas as pd
    from datetime import datetime, timedelta

    # Read from mounted PVC path
    df = pd.read_csv("/data/metrics.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Resample to minute frequency
    df = df.set_index("timestamp").resample("T").mean().reset_index()
    
    # Get last N hours of data
    # cutoff_time = df["timestamp"].max() - timedelta(hours=hours_back)
    # df_filtered = df[df["timestamp"] >= cutoff_time].copy()
    
    df_filtered = df[
        (df["timestamp"] >= "2024-12-05 10:00") & 
        (df["timestamp"] <= "2024-12-05 16:00")
    ].copy()
    
    # Save filtered data for next step
    df_filtered.to_csv("/processed/data.csv", index=False)


@dsl.component(
    base_image="python:3.10",
    packages_to_install=["tensorflow", "numpy", "pandas", "model_registry", "scikit-learn"],
)
def train_model(model_name: str, model_version: str, author: str):
    """Train LSTM model for time series forecasting"""
    import tensorflow as tf
    import numpy as np
    import pandas as pd
    import os
    from model_registry import ModelRegistry
    from sklearn.preprocessing import MinMaxScaler
    
    # Load the processed data
    df = pd.read_csv('/processed/data.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Scale the data
    scaler = MinMaxScaler()
    scaled_data = scaler.fit_transform(df[['cpu_usage']])
    
    # Create sequences for training
    sequence_length = 60  # Input sequence length (60 minutes)
    prediction_length = 60  # Prediction length (60 minutes)
    
    X, y = [], []
    for i in range(len(scaled_data) - sequence_length - prediction_length):
        X.append(scaled_data[i:(i + sequence_length)])
        y.append(scaled_data[(i + sequence_length):(i + sequence_length + prediction_length)])
    
    X = np.array(X)
    y = np.array(y)
    
    # Split into train and validation
    train_size = int(len(X) * 0.8)
    X_train, X_val = X[:train_size], X[train_size:]
    y_train, y_val = y[:train_size], y[train_size:]
    
    # Define model architecture
    model = tf.keras.Sequential([
        tf.keras.layers.LSTM(64, return_sequences=True, input_shape=(sequence_length, 1)),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.LSTM(32),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(prediction_length)
    ])
    
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    
    # Add early stopping
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=5,
            restore_best_weights=True
        )
    ]
    
    # Train model
    history = model.fit(
        X_train, y_train,
        epochs=50,
        batch_size=32,
        validation_data=(X_val, y_val),
        callbacks=callbacks
    )
    
    # Create versioned directory structure
    model_dir = f'/models/{model_name}'
    version_dir = os.path.join(model_dir, model_version)
    os.makedirs(version_dir, exist_ok=True)
    
    # Save model
    model.export(version_dir)
    
    # Prepare metadata TODO
    # metadata = {
    #     "custom_properties": {
    #         "validation_loss": str(float(history.history['val_loss'][-1])),
    #         "validation_mae": str(float(history.history['val_mae'][-1])),
    #         "training_loss": str(float(history.history['loss'][-1])),
    #         "training_mae": str(float(history.history['mae'][-1])),
    #     }
    # }
    
    # Register model
    registry = ModelRegistry(
        server_address="http://model-registry-service.kubeflow.svc.cluster.local",
        port=8080,
        author=author,
        is_secure=False
    )
    
    registered_model = registry.register_model(
        model_name,
        f"pvc://model-registry-pvc/{model_name}",
        model_format_name="tensorflow",
        model_format_version="2.0",
        version=model_version,
        description="Simple LSTM model for CPU usage prediction",
        # metadata=metadata TODO
    )

@dsl.component(
    base_image="python:3.10", packages_to_install=["kserve", "model_registry"]
)
def deploy_model(
    model_name: str, model_version: str, namespace: str = "kubeflow-user-example-com"
):
    """Deploy model to KServe with rolling updates"""
    from kubernetes import client
    from kserve import KServeClient, constants
    from model_registry import ModelRegistry
    from kserve import V1beta1InferenceService
    from kserve import V1beta1InferenceServiceSpec
    from kserve import V1beta1PredictorSpec
    from kserve import V1beta1TFServingSpec

    # Initialize clients
    kserve_client = KServeClient()
    
    # Initialize model registry
    registry = ModelRegistry(
        server_address="http://model-registry-service.kubeflow.svc.cluster.local",
        port=8080,
        author="system",
        is_secure=False,
    )

    # Get model details from registry
    model = registry.get_registered_model(model_name)
    version = registry.get_model_version(model_name, model_version)
    
    # Define rolling update strategy
    strategy = client.V1RollingUpdateDeployment(
        max_surge="25%",
        max_unavailable="25%"
    )
    
    # Create or update InferenceService
    isvc = V1beta1InferenceService(
        api_version=constants.KSERVE_V1BETA1,
        kind=constants.KSERVE_KIND,
        metadata=client.V1ObjectMeta(
            name=model_name,
            namespace=namespace,
        ),
        spec=V1beta1InferenceServiceSpec(
            predictor=V1beta1PredictorSpec(
                min_replicas=1,
                max_replicas=3,
                tensorflow=V1beta1TFServingSpec(
                    storage_uri=f"pvc://metrics-data-pvc/{model_name}",
                    resources={
                        "requests": {"cpu": "100m", "memory": "1Gi"},
                        "limits": {"cpu": "1", "memory": "2Gi"}
                    }
                )
            )
        )
    )

    try:
        # Check if service exists
        existing_svc = kserve_client.get(
            name=model_name,
            namespace=namespace,
            version=constants.KSERVE_V1BETA1
        )
        # Update existing service
        kserve_client.patch(
            name=model_name,
            isvc=isvc,
            namespace=namespace,
            version=constants.KSERVE_V1BETA1
        )
    except:
        # Create new service
        kserve_client.create(isvc)


@dsl.pipeline(name="Time Series Forecasting Pipeline")
def forecasting_pipeline(
    data_pvc: str = "metrics-data-pvc",
    processed_data_pvc: str = "metrics-data-pvc",
    model_pvc: str = "metrics-data-pvc",
    model_name: str = "ts-forecaster",
    model_version: str = "1",
    author: str = "system",
    namespace: str = "kubeflow-user-example-com",
):
    # Prepare data
    prepare_step = prepare_data(hours_back=24)
    prepare_step.set_caching_options(False)
    kubernetes.mount_pvc(prepare_step, pvc_name=data_pvc, mount_path="/data")
    kubernetes.mount_pvc(
        prepare_step, pvc_name=processed_data_pvc, mount_path="/processed"
    )

    # Train model
    train_step = train_model(
        model_name=model_name, model_version=model_version, author=author
    )
    kubernetes.mount_pvc(
        train_step, pvc_name=processed_data_pvc, mount_path="/processed"
    )
    kubernetes.mount_pvc(train_step, pvc_name=model_pvc, mount_path="/models")

    # Deploy model
    deploy_step = deploy_model(
        model_name=model_name, model_version=model_version, namespace=namespace
    )

    # Define execution order
    train_step.after(prepare_step)
    deploy_step.after(train_step)


if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=forecasting_pipeline, package_path="forecasting_pipeline.yaml"
    )