import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
import logging
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CPUPredictor:
    def __init__(self, model_url, input_file, output_file, sequence_length=60):
        """
        Initialize the predictor with configuration parameters.
        
        Args:
            model_url: URL of the deployed model
            input_file: Path to metrics.csv file
            output_file: Path to save predictions
            sequence_length: Number of minutes to use for prediction (default: 60)
        """
        self.model_url = model_url
        self.input_file = input_file
        self.output_file = output_file
        self.sequence_length = sequence_length
        self.scaler = MinMaxScaler()
        self.last_processed_time = None
        
    def prepare_data(self, df):
        """
        Prepare the input data for prediction.
        
        Args:
            df: DataFrame containing the raw metrics data
            
        Returns:
            Scaled and formatted input data ready for prediction
        """
        # Convert timestamp to datetime if it's not already
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df_resampled = df.set_index('timestamp').resample('min').mean()
        
        df_resampled = df_resampled.ffill()
        
        # Get the last sequence_length minutes of data
        last_sequence = df_resampled['cpu_usage'].values[-self.sequence_length:]
        
        # Fit and transform the data
        scaled_data = self.scaler.fit_transform(last_sequence.reshape(-1, 1))
        
        # Reshape for model input (batch_size, sequence_length, features)
        model_input = scaled_data.reshape(1, self.sequence_length, 1)
        
        return model_input, df_resampled.index[-1]

    def make_prediction(self, model_input):
        """
        Send the prepared data to the model and get predictions.
        
        Args:
            model_input: Prepared and scaled input data
            
        Returns:
            Array of predicted values
        """
        # Prepare the request payload
        payload = {
            "instances": model_input.tolist()
        }

        try:
            # Make prediction request
            response = requests.post(self.model_url, json=payload)
            response.raise_for_status()
            
            # Parse response
            predictions = np.array(response.json()['predictions'])
            
            # Inverse transform the predictions
            predictions_original_scale = self.scaler.inverse_transform(predictions.reshape(-1, 1))
            
            return predictions_original_scale
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making prediction request: {e}")
            return None

    def save_predictions(self, predictions, last_timestamp):
        """
        Save the predictions to a CSV file.
        
        Args:
            predictions: Array of predicted values
            last_timestamp: Timestamp of the last input data point
        """
        # Generate timestamp for each prediction (one per minute)
        timestamps = [last_timestamp + timedelta(minutes=i+1) for i in range(len(predictions))]
        
        # Create prediction DataFrame
        pred_df = pd.DataFrame({
            'timestamp': timestamps,
            'predicted_cpu_usage': predictions.flatten()
        })
        
        # Append to existing predictions file or create new one
        try:
            existing_preds = pd.read_csv(self.output_file)
            existing_preds['timestamp'] = pd.to_datetime(existing_preds['timestamp'])
            
            # Remove any overlapping predictions
            existing_preds = existing_preds[existing_preds['timestamp'] < timestamps[0]]
            
            # Concatenate and save
            final_preds = pd.concat([existing_preds, pred_df])
            
        except FileNotFoundError:
            final_preds = pred_df
            
        final_preds.to_csv(self.output_file, index=False)
        logger.info(f"Saved predictions for timestamps from {timestamps[0]} to {timestamps[-1]}")

    def run_prediction_loop(self, interval_seconds=60):
        """
        Main loop to continuously make predictions.
        
        Args:
            interval_seconds: How often to make new predictions (default: 60 seconds)
        """
        logger.info("Starting prediction loop...")
        
        while True:
            try:
                # Read the latest data
                df = pd.read_csv(self.input_file)
                
                # Check if we have new data to process
                latest_time = pd.to_datetime(df['timestamp']).max()
                
                if self.last_processed_time is None or latest_time > self.last_processed_time:
                    # Prepare data
                    model_input, last_timestamp = self.prepare_data(df)
                    
                    # Make prediction
                    predictions = self.make_prediction(model_input)
                    
                    if predictions is not None:
                        # Save predictions
                        self.save_predictions(predictions, last_timestamp)
                        self.last_processed_time = latest_time
                    
                # Wait for next interval
                time.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in prediction loop: {e}")
                time.sleep(interval_seconds)  # Wait before retrying

if __name__ == "__main__":
    # Configuration
    MODEL_URL = os.getenv("MODEL_URL", "http://localhost:8080/v1/models/ts-forecaster:predict")
    INPUT_FILE = os.getenv("INPUT_FILE", "metrics.csv")
    OUTPUT_FILE = os.getenv("OUTPUT_FILE", "predicted.csv")
    
    # Initialize and run predictor
    predictor = CPUPredictor(
        model_url=MODEL_URL,
        input_file=INPUT_FILE,
        output_file=OUTPUT_FILE
    )
    
    predictor.run_prediction_loop()