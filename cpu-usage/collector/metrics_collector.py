import time
import pandas as pd
import numpy as np
from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self,
        prom_url=None,  # Remove default value
        storage_path='/data/metrics.csv',
        query_interval=1):  # seconds
        
        # Get Prometheus URL from environment variable with fallback
        self.prom_url = prom_url or os.getenv('PROMETHEUS_URL', 'http://prometheus-server:9090')
        logger.info(f"Using Prometheus URL: {self.prom_url}")

        self.prom = PrometheusConnect(url=self.prom_url, disable_ssl=True)
        self.storage_path = storage_path
        self.query_interval = query_interval or os.getenv('QUERY_INTERVAL', 1)
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        # Initialize or load existing CSV
        if not os.path.exists(self.storage_path):
            self._initialize_csv()
            
    def _initialize_csv(self):
        """Initialize empty CSV file with headers"""
        df = pd.DataFrame(columns=['timestamp', 'cpu_usage'])
        df.to_csv(self.storage_path, index=False)
        logger.info(f"Initialized new CSV file at {self.storage_path}")

    def query_prometheus(self):
        """Query Prometheus for CPU usage metrics"""
        try:
            # Query for nginx CPU usage
            query = 'sum(rate(container_cpu_usage_seconds_total{container="nginx"}[5m]))'
            result = self.prom.custom_query(query)
            
            if result and len(result) > 0:
                # Extract the latest value
                value = float(result[0]['value'][1])
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                return timestamp, value
            return None
        except Exception as e:
            logger.error(f"Error querying Prometheus: {e}")
            return None

    def append_to_csv(self, data):
        """Append new data to CSV file"""
        if data is None:
            return
        
        timestamp, value = data
        new_row = pd.DataFrame({
            'timestamp': [timestamp],
            'cpu_usage': [value]
        })
        
        try:
            new_row.to_csv(self.storage_path, mode='a', header=False, index=False)
            logger.info(f"Appended data: {timestamp}, {value}")
        except Exception as e:
            logger.error(f"Error appending to CSV: {e}")

    def run_forever(self):
        """Run the collector indefinitely"""
        logger.info("Starting metrics collection...")
        while True:
            try:
                data = self.query_prometheus()
                self.append_to_csv(data)
                time.sleep(self.query_interval)
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                time.sleep(self.query_interval)

if __name__ == "__main__":
    collector = MetricsCollector()
    collector.run_forever()