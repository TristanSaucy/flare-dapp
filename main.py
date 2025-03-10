#!/usr/bin/env python3
"""
Confidential Space Application
This application retrieves an encrypted key from a GCS bucket, decrypts it using KMS,
and then logs a message every 5 seconds to Google Cloud Logging.
"""

import os
import time
import logging
import sys
import json
import base64
import requests
import google.cloud.logging
from google.cloud import storage
from google.cloud import kms

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

def get_metadata(metadata_key):
    """Get metadata from the Confidential Space VM metadata server."""
    try:
        url = f"http://metadata.google.internal/computeMetadata/v1/instance/attributes/{metadata_key}"
        headers = {"Metadata-Flavor": "Google"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.text
        else:
            logger.warning(f"Failed to get metadata for key {metadata_key}: HTTP {response.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Error getting metadata for key {metadata_key}: {str(e)}")
        return None

def get_env_var(var_name, default=None, required=False):
    """Get an environment variable with fallback to metadata."""
    # First try environment variable
    value = os.environ.get(var_name)
    
    # If not found, try metadata
    if not value:
        value = get_metadata(var_name)
    
    # If still not found, use default or raise error if required
    if not value:
        if required and default is None:
            error_msg = f"Required variable {var_name} is not set in environment or metadata"
            logger.error(error_msg)
            log_to_cloud("ERROR", error_msg)
            raise ValueError(error_msg)
        value = default
    
    return value

def download_encrypted_key(bucket_name, key_object_name):
    """Download an encrypted key from a GCS bucket."""
    try:
        logger.info(f"Downloading encrypted key from gs://{bucket_name}/{key_object_name}")
        log_to_cloud("INFO", "Downloading encrypted key", bucket=bucket_name, object=key_object_name)
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(key_object_name)
        
        encrypted_key = blob.download_as_bytes()
        logger.info(f"Downloaded encrypted key ({len(encrypted_key)} bytes)")
        log_to_cloud("INFO", "Downloaded encrypted key", size_bytes=len(encrypted_key))
        
        return encrypted_key
    except Exception as e:
        error_msg = f"Failed to download encrypted key: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_to_cloud("ERROR", error_msg, error=str(e))
        raise

def decrypt_key(encrypted_key, kms_key_name):
    """Decrypt a key using Cloud KMS."""
    try:
        logger.info(f"Decrypting key using KMS key: {kms_key_name}")
        log_to_cloud("INFO", "Decrypting key", kms_key=kms_key_name)
        
        kms_client = kms.KeyManagementServiceClient()
        
        # Decrypt the key
        decrypt_response = kms_client.decrypt(
            request={
                "name": kms_key_name,
                "ciphertext": encrypted_key,
            }
        )
        
        decrypted_key = decrypt_response.plaintext
        logger.info(f"Key decrypted successfully ({len(decrypted_key)} bytes)")
        log_to_cloud("INFO", "Key decrypted successfully", size_bytes=len(decrypted_key))
        
        return decrypted_key
    except Exception as e:
        error_msg = f"Failed to decrypt key: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_to_cloud("ERROR", error_msg, error=str(e))
        raise

def main():
    """Main entry point for the application."""
    try:
        logger.info("Starting Confidential Space application")
        log_to_cloud("INFO", "Starting Confidential Space application")
        
        # Log metadata availability
        try:
            logger.info("Checking metadata server availability...")
            project_id = get_metadata("project-id")
            if project_id:
                logger.info(f"Metadata server is available. Project ID: {project_id}")
                log_to_cloud("INFO", "Metadata server is available", project_id=project_id)
            else:
                logger.warning("Metadata server is not available or project-id not found")
                log_to_cloud("WARNING", "Metadata server is not available or project-id not found")
        except Exception as e:
            logger.warning(f"Error checking metadata server: {str(e)}")
        
        # Get configuration from environment variables or metadata
        input_bucket = get_env_var("INPUT_BUCKET_NAME", required=True)
        key_object_name = get_env_var("KEY_OBJECT_NAME", default="encrypted-key.enc")
        kms_key_name = get_env_var("KMS_KEY_NAME", required=True)
        
        logger.info(f"Using input bucket: {input_bucket}")
        logger.info(f"Using key object: {key_object_name}")
        logger.info(f"Using KMS key: {kms_key_name}")
        
        # Download and decrypt the key
        encrypted_key = download_encrypted_key(input_bucket, key_object_name)
        decrypted_key = decrypt_key(encrypted_key, kms_key_name)
        
        # Log success (but don't log the actual key content for security)
        logger.info("Successfully retrieved and decrypted the key")
        log_to_cloud("INFO", "Successfully retrieved and decrypted the key", 
                    key_length=len(decrypted_key))
        
        # For demonstration, print the first few characters of the key
        # In a real application, you would use the key for its intended purpose
        key_preview = decrypted_key[:10].decode('utf-8') + "..." if len(decrypted_key) > 10 else decrypted_key.decode('utf-8')
        logger.info(f"Key preview: {key_preview}")
        
        # Log a message every 5 seconds
        counter = 0
        while True:
            counter += 1
            message = f"Heartbeat #{counter} - Application is running with decrypted key"
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