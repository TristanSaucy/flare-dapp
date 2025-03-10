#!/usr/bin/env python3
"""
Minimal Confidential Space Application
This version simply logs a message every 5 seconds to Google Cloud Logging.
"""

import os
import time
import logging
import sys
import json
import google.cloud.logging

# Set up Cloud Logging client
try:
    cloud_logger_client = google.cloud.logging.Client()
    cloud_logger = cloud_logger_client.logger('confidential-space-app')
    USE_CLOUD_LOGGING = True
    print("Cloud Logging initialized successfully")
except Exception as e:
    print(f"Failed to initialize Cloud Logging: {str(e)}")
    USE_CLOUD_LOGGING = False

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def log_to_cloud(severity, message, **kwargs):
    """Log to Cloud Logging with structured data."""
    if not USE_CLOUD_LOGGING:
        logger.info(f"Would log to cloud: {severity} - {message}")
        return
    
    try:
        struct_data = {
            "message": message,
            "component": "confidential-space-app",
            **kwargs
        }
        cloud_logger.log_struct(struct_data, severity=severity)
    except Exception as e:
        logger.error(f"Failed to log to Cloud Logging: {str(e)}")

def main():
    """Main entry point for the application."""
    try:
        logger.info("Starting minimal confidential space application")
        log_to_cloud("INFO", "Starting minimal confidential space application")
        
        # Log a message every 5 seconds
        counter = 0
        while True:
            counter += 1
            message = f"Heartbeat #{counter} - Application is running"
            logger.info(message)
            log_to_cloud("INFO", message, counter=counter)
            time.sleep(5)
            
    except Exception as e:
        error_message = f"Application failed: {str(e)}"
        logger.error(error_message, exc_info=True)
        if USE_CLOUD_LOGGING:
            log_to_cloud("ERROR", error_message, traceback=str(e))
        # Sleep for a short time to ensure logs are flushed before container exits
        time.sleep(5)
        sys.exit(1)

if __name__ == "__main__":
    main() 