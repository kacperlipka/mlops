import pandas as pd
import numpy as np
import requests
import time
import os
from datetime import datetime, timedelta
import logging

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Predictor:
    def __init__(self, input_path, output_path, model_url):
        """
        Initialize the predictor.
        
        Args:
            input_path: Path to the input CSV file with metrics
            output_path: Path where predictions will be saved
            model_url: URL of the deployed model endpoint
        """
        self.input_path = input_path
        self.output_path = output_path
        self.model_url = model_url
        self.last_prediction_time = None
    
    def predict_next_60_minutes(self):
        """
        Make predictions for the next 60 minutes based on the last 60 minutes of data.
        
        Returns:
            tuple: (predictions array, last timestamp) or (None, None) if error occurs
        """
        try:
            df = pd.read_csv(self.input_path, parse_dates=["timestamp"], index_col="timestamp")
            df = df.resample("1min").mean().ffill()
            last_60_minutes = np.array(df['cpu_usage'].tail(60))
            last_timestamp = df.index[-1]
            
            # Check if we have enough data
            if len(last_60_minutes) < 60:
                logger.error(f"Insufficient data points: {len(last_60_minutes)}")
                return None, None
            
            model_input = last_60_minutes.reshape(1, 60, 1)
            
            # Prepare payload for API request
            payload = {
                "instances": model_input.tolist()
            }
            
            # Make prediction request
            response = requests.post(self.model_url, json=payload)
            response.raise_for_status()
            predictions = np.array(response.json()["predictions"]).flatten()
            
            return predictions, last_timestamp
            
        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            return None, None
    
    def save_predictions(self, predictions, last_timestamp):
        """
        Save predictions to CSV file.
        
        Args:
            predictions: Array of predicted values
            last_timestamp: Timestamp of the last input data point
        """
        try:
            # Generate timestamps for predictions
            future_timestamps = [last_timestamp + pd.Timedelta(minutes=i+1) for i in range(60)]
            
            # Create DataFrame with predictions
            predictions_df = pd.DataFrame({
                'timestamp': future_timestamps,
                'predicted_cpu_usage': predictions
            })
            
            # If file exists, append new predictions
            if os.path.exists(self.output_path):
                existing_df = pd.read_csv(self.output_path, parse_dates=['timestamp'])
                existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'])
                
                # Remove predictions that overlap with new ones
                existing_df = existing_df[existing_df['timestamp'] < future_timestamps[0]]
                
                # Concatenate existing and new predictions
                predictions_df = pd.concat([existing_df, predictions_df])
            
            # Save to file
            predictions_df.to_csv(self.output_path, index=False)
            logger.info(f"Saved predictions from {future_timestamps[0]} to {future_timestamps[-1]}")
            
        except Exception as e:
            logger.error(f"Error while saving predictions: {e}")
    
    def run_prediction_loop(self, interval_seconds=60):
        """
        Run the main prediction loop.
        
        Args:
            interval_seconds: Number of seconds to wait between predictions
        """
        logger.info("Starting prediction loop...")
        
        while True:
            try:
                # Check if input file exists
                if not os.path.exists(self.input_path):
                    logger.warning(f"Input file not found: {self.input_path}")
                    time.sleep(interval_seconds)
                    continue
                
                # Check for new data
                df = pd.read_csv(self.input_path, parse_dates=["timestamp"])
                current_time = pd.to_datetime(df['timestamp']).max()
                
                # Make predictions if new data is available
                if self.last_prediction_time is None or current_time > self.last_prediction_time:
                    predictions, last_timestamp = self.predict_next_60_minutes()
                    
                    if predictions is not None and last_timestamp is not None:
                        self.save_predictions(predictions, last_timestamp)
                        self.last_prediction_time = current_time
                else:
                    logger.info("No new data to process")
                
                # Wait for next iteration
                time.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in prediction loop: {e}")
                time.sleep(interval_seconds)

if __name__ == "__main__":
    # Initialize and run the predictor
    predictor = Predictor(
        input_path="/data/metrics.csv",
        output_path="/data/predictions.csv",
        model_url="http://cpu-usage-forecaster-predictor-00001-private/v1/models/cpu-usage-forecaster:predict"
    )
    
    predictor.run_prediction_loop()