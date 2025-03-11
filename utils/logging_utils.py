"""
Logging utilities for the Confidential Space application.
"""
import logging
import sys
import datetime
import google.cloud.logging

def setup_logging():
    """Set up logging for the application."""
    # Set up Cloud Logging client
    try:
        cloud_logger_client = google.cloud.logging.Client()
        cloud_logger = cloud_logger_client.logger('confidential-space-app')
        USE_CLOUD_LOGGING = True
        print("Cloud Logging initialized successfully")
    except Exception as e:
        print(f"Failed to initialize Cloud Logging: {str(e)}")
        cloud_logger = None
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
    
    return logger, cloud_logger, USE_CLOUD_LOGGING

def log_to_cloud(cloud_logger, severity, message, use_cloud_logging=True, **kwargs):
    """Log to Cloud Logging with structured data."""
    if not use_cloud_logging or cloud_logger is None:
        return
    
    try:
        struct_data = {
            "message": message,
            "component": "confidential-space-app",
            **kwargs
        }
        cloud_logger.log_struct(struct_data, severity=severity)
    except Exception as e:
        print(f"Failed to log to Cloud Logging: {str(e)}")

def log_message(severity, message, recent_logs=None, logger=None, cloud_logger=None, use_cloud_logging=False, **kwargs):
    """Log a message to both standard logging and Cloud Logging, and add to recent logs."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} - {severity} - {message}"
    
    # Add to recent logs if provided
    if recent_logs is not None:
        recent_logs.appendleft(log_entry)
    
    # Log to standard logging if logger provided
    if logger:
        if severity == "ERROR":
            logger.error(message)
        elif severity == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
    
    # Log to Cloud Logging if provided
    if cloud_logger:
        log_to_cloud(cloud_logger, severity, message, use_cloud_logging, **kwargs) 