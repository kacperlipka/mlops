import pandas as pd
import numpy as np
from sklearn.metrics import r2_score, mean_squared_error
from datetime import datetime, timedelta
from prometheus_client import start_http_server, Gauge
import time

# Initialize Prometheus metrics
r2_metric = Gauge('model_r2_score', 'R-squared score of the model')
rmse_metric = Gauge('model_rmse', 'Root mean squared error of the model')
mse_metric = Gauge('model_mse', 'Mean squared error of the model')

predicted_value = Gauge('predicted_value', 'Predicted value of the CPU usage')
actual_value = Gauge('actual_value', 'Actual value of the CPU usage')

def calculate_metrics(actual_data_path="/data/metrics.csv", pred_data_path="/data/predictions.csv", cutoff_time_hours=1):
    try:
        # Read and process data
        actual_df = pd.read_csv(actual_data_path, parse_dates=["timestamp"], index_col="timestamp")
        pred_df = pd.read_csv(pred_data_path, parse_dates=["timestamp"], index_col="timestamp")
        
        # Resample actual data to 1-minute intervals
        actual_df = actual_df.resample("1min").mean()
        
        # Calculate time window
        max_time = actual_df.index.max()
        cutoff_time = max_time - timedelta(hours=cutoff_time_hours)
        
        # Filter data for the last hour
        actual_df = actual_df[actual_df.index > cutoff_time]
        pred_df = pred_df[(max_time >= pred_df.index) & (pred_df.index > cutoff_time)]
        
        # Extract values for comparison
        y_true = actual_df["cpu_usage"]
        y_pred = pred_df["predicted_cpu_usage"]
        
        
        # Calculate metrics
        r2 = r2_score(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mse = mean_squared_error(y_true, y_pred)
        
        actual_cpu = actual_df[actual_df.index == max_time]["cpu_usage"].iloc[0]
        actual_pred = pred_df[pred_df.index == max_time]["predicted_cpu_usage"].iloc[0]
        
        # Update Prometheus metrics
        r2_metric.set(r2)
        rmse_metric.set(rmse)
        mse_metric.set(mse)
        predicted_value.set(actual_pred)
        actual_value.set(actual_cpu)
        
        print(f"Metrics updated at {datetime.now()}")
        print(f"R2: {r2:.4f}")
        print(f"RMSE: {rmse:.4f}")
        print(f"MSE: {mse:.4f}")
        print(f"Actual CPU usage: {actual_cpu:.4f}")
        print(f"Predicted CPU usage: {actual_pred:.4f}")
        print("-" * 50)
        
    except Exception as e:
        print(f"Error occurred: {e}")

def main():
    # Start up the server to expose metrics
    start_http_server(8000)
    print("Metrics server started at port 8000")
    
    while True:
        calculate_metrics()
        time.sleep(60)  # Wait 5 minutes before next update

if __name__ == "__main__":
    main()