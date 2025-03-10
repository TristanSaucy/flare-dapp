#!/usr/bin/env python3
"""
Confidential Space Application
This application retrieves an encrypted key from a GCS bucket, decrypts it using KMS,
and then provides a web interface to monitor the application status and chat with Gemini.
"""

import os
import time
import logging
import sys
import json
import base64
import requests
import threading
import datetime
from collections import deque
import google.cloud.logging
from google.cloud import storage
from google.cloud import kms
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, GenerationConfig
from flask import Flask, render_template, request, jsonify

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

# Create Flask app
app = Flask(__name__)

# Global variables for application state
start_time = datetime.datetime.now()
heartbeat_count = 0
key_retrieved = False
recent_logs = deque(maxlen=50)  # Store the 50 most recent log entries
config = {
    'input_bucket': None,
    'key_object': None,
    'project_id': None
}
decrypted_key = None
gemini_model = None

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

def log_message(severity, message, **kwargs):
    """Log a message to both standard logging and Cloud Logging, and add to recent logs."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} - {severity} - {message}"
    
    # Add to recent logs
    recent_logs.appendleft(log_entry)
    
    # Log to standard logging
    if severity == "ERROR":
        logger.error(message)
    elif severity == "WARNING":
        logger.warning(message)
    else:
        logger.info(message)
    
    # Log to Cloud Logging
    log_to_cloud(severity, message, **kwargs)

def get_metadata(metadata_key):
    """Get metadata from the Confidential Space VM metadata server."""
    try:
        url = f"http://metadata.google.internal/computeMetadata/v1/instance/attributes/{metadata_key}"
        headers = {"Metadata-Flavor": "Google"}
        log_message("DEBUG", f"Requesting metadata for key: {metadata_key}")
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            value = response.text
            # Truncate long values in logs for privacy/security
            log_value = value[:20] + "..." if len(value) > 20 else value
            log_message("DEBUG", f"Successfully retrieved metadata for key {metadata_key}: {log_value}")
            return value
        else:
            log_message("WARNING", f"Failed to get metadata for key {metadata_key}: HTTP {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        log_message("WARNING", f"Could not connect to metadata server. This might not be a Confidential Space VM.")
        return None
    except requests.exceptions.Timeout:
        log_message("WARNING", f"Timeout while connecting to metadata server for key {metadata_key}")
        return None
    except Exception as e:
        log_message("WARNING", f"Error getting metadata for key {metadata_key}: {str(e)}")
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
            log_message("ERROR", error_msg)
            raise ValueError(error_msg)
        value = default
    
    return value

def download_encrypted_key(bucket_name, key_object_name):
    """Download an encrypted key from a GCS bucket."""
    try:
        log_message("INFO", f"Downloading encrypted key from gs://{bucket_name}/{key_object_name}", 
                   bucket=bucket_name, object=key_object_name)
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(key_object_name)
        
        encrypted_key = blob.download_as_bytes()
        log_message("INFO", f"Downloaded encrypted key ({len(encrypted_key)} bytes)", 
                   size_bytes=len(encrypted_key))
        
        return encrypted_key
    except Exception as e:
        error_msg = f"Failed to download encrypted key: {str(e)}"
        log_message("ERROR", error_msg, error=str(e))
        raise

def decrypt_key(encrypted_key, kms_key_name):
    """Decrypt a key using Cloud KMS."""
    try:
        log_message("INFO", f"Decrypting key using KMS key: {kms_key_name}", kms_key=kms_key_name)
        
        kms_client = kms.KeyManagementServiceClient()
        
        # Decrypt the key
        decrypt_response = kms_client.decrypt(
            request={
                "name": kms_key_name,
                "ciphertext": encrypted_key,
            }
        )
        
        decrypted_key = decrypt_response.plaintext
        log_message("INFO", f"Key decrypted successfully ({len(decrypted_key)} bytes)", 
                   size_bytes=len(decrypted_key))
        
        return decrypted_key
    except Exception as e:
        error_msg = f"Failed to decrypt key: {str(e)}"
        log_message("ERROR", error_msg, error=str(e))
        raise

def initialize_gemini():
    """Initialize the Vertex AI client for Gemini."""
    global gemini_model
    
    try:
        # Get project ID from environment or metadata
        project_id = get_env_var("PROJECT_ID")
        if not project_id:
            try:
                project_id = get_metadata("PROJECT_ID")
                log_message("INFO", f"Retrieved project ID from metadata: {project_id}")
            except Exception as e:
                log_message("WARNING", f"Failed to get project ID from metadata: {str(e)}")
                try:
                    # Fallback to metadata server project ID
                    project_id = get_metadata("project/project-id")
                    log_message("INFO", f"Retrieved project ID from metadata server: {project_id}")
                except Exception as e:
                    log_message("WARNING", f"Failed to get project ID from metadata server: {str(e)}")
        
        # Get region from environment or metadata
        location = get_env_var("REGION", "us-central1")
        if location == "us-central1":  # If using default, try metadata
            try:
                metadata_region = get_metadata("REGION")
                if metadata_region:
                    location = metadata_region
                    log_message("INFO", f"Retrieved region from metadata: {location}")
            except Exception as e:
                log_message("WARNING", f"Failed to get region from metadata: {str(e)}")
        
        if not project_id:
            log_message("WARNING", "No project ID found. Chat functionality will be limited.")
            return False
        
        log_message("INFO", f"Initializing Vertex AI with project={project_id}, location={location}")
        
        # Initialize Vertex AI
        aiplatform.init(project=project_id, location=location)
        
        # Store the project and location for later use
        gemini_model = {
            "project_id": project_id,
            "location": location,
            "initialized": True
        }
        
        log_message("INFO", "Vertex AI initialized successfully for Gemini")
        return True
    except Exception as e:
        error_msg = f"Failed to initialize Vertex AI for Gemini: {str(e)}"
        log_message("ERROR", error_msg, error=str(e))
        return False

def get_gemini_response(prompt):
    """Get a response from Gemini via Vertex AI."""
    global gemini_model
    
    try:
        if not gemini_model or not gemini_model.get("initialized", False):
            log_message("INFO", "Gemini model not initialized, attempting to initialize now")
            if not initialize_gemini():
                log_message("ERROR", "Failed to initialize Gemini model")
                return "I'm sorry, but I'm not able to respond right now due to configuration issues. Please check the logs for more information."
        
        log_message("INFO", f"Sending prompt to Gemini (length: {len(prompt)})")
        
        # Get a Vertex AI Gemini model
        model_name = "gemini-2.0-pro-exp-02-05"  # Use the experimental Gemini 2.0 Pro model
        log_message("DEBUG", f"Creating model instance for {model_name}")
        
        # Set up generation config
        generation_config = GenerationConfig(
            temperature=0.7,
            max_output_tokens=1024,
            top_p=0.95,
            top_k=40
        )
        
        # Create the model
        model = GenerativeModel(model_name)
        
        # Generate content
        log_message("DEBUG", "Calling Vertex AI generate_content method")
        response = model.generate_content(
            contents=prompt,
            generation_config=generation_config
        )
        
        # Extract the text from the response
        response_text = response.text
        log_message("INFO", f"Received response from Gemini (length: {len(response_text)})")
        return response_text
    except Exception as e:
        error_msg = f"Failed to get Gemini response: {str(e)}"
        log_message("ERROR", error_msg, error=str(e))
        return f"I encountered an error while processing your request. Please try again later or check the application logs for more information."

def get_uptime():
    """Get the application uptime as a formatted string."""
    uptime = datetime.datetime.now() - start_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days} days, {hours} hours, {minutes} minutes"
    elif hours > 0:
        return f"{hours} hours, {minutes} minutes"
    else:
        return f"{minutes} minutes, {seconds} seconds"

@app.route('/')
def index():
    """Render the main web interface."""
    return render_template('index.html', 
                          key_retrieved=key_retrieved,
                          uptime=get_uptime(),
                          heartbeat_count=heartbeat_count,
                          input_bucket=config['input_bucket'],
                          key_object=config['key_object'],
                          project_id=config['project_id'],
                          logs=list(recent_logs))

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    """Handle the chat interface."""
    if request.method == 'POST':
        # Handle AJAX request
        if request.is_json:
            data = request.get_json()
            user_input = data.get('user_input', '')
            
            if not user_input:
                return jsonify({'error': 'No input provided'})
            
            # Get response from Gemini
            response = get_gemini_response(user_input)
            
            return jsonify({'response': response})
        
        # Handle form submission (fallback)
        user_input = request.form.get('user_input', '')
        if not user_input:
            return render_template('chat.html', error='No input provided')
        
        # Get response from Gemini
        response = get_gemini_response(user_input)
        
        return render_template('chat.html', user_input=user_input, response=response)
    
    # GET request - just show the chat interface
    return render_template('chat.html')

def heartbeat_thread():
    """Background thread that logs a heartbeat message periodically."""
    global heartbeat_count
    
    while True:
        heartbeat_count += 1
        message = f"Heartbeat #{heartbeat_count} - Application is running"
        log_message("INFO", message, counter=heartbeat_count)
        time.sleep(5)

def main():
    """Main entry point for the application."""
    global key_retrieved, config, decrypted_key
    
    try:
        log_message("INFO", "Starting Confidential Space application")
        
        # Log metadata availability
        try:
            log_message("INFO", "Checking metadata server availability...")
            project_id = get_metadata("project-id")
            if project_id:
                log_message("INFO", f"Metadata server is available. Project ID: {project_id}")
                config['project_id'] = project_id
            else:
                log_message("WARNING", "Metadata server is not available or project-id not found")
        except Exception as e:
            log_message("WARNING", f"Error checking metadata server: {str(e)}")
        
        # Get configuration from environment variables or metadata
        input_bucket = get_env_var("INPUT_BUCKET_NAME", required=True)
        key_object_name = get_env_var("KEY_OBJECT_NAME", default="encrypted-key.enc")
        kms_key_name = get_env_var("KMS_KEY_NAME", required=True)
        
        config['input_bucket'] = input_bucket
        config['key_object'] = key_object_name
        
        log_message("INFO", f"Using input bucket: {input_bucket}")
        log_message("INFO", f"Using key object: {key_object_name}")
        log_message("INFO", f"Using KMS key: {kms_key_name}")
        
        # Initialize Gemini API
        log_message("INFO", "Initializing Vertex AI for Gemini")
        if initialize_gemini():
            log_message("INFO", "Vertex AI for Gemini initialized successfully")
        else:
            log_message("WARNING", "Failed to initialize Vertex AI for Gemini. Chat functionality may be limited.")
        
        # Start the heartbeat thread
        thread = threading.Thread(target=heartbeat_thread, daemon=True)
        thread.start()
        
        # Try to download and decrypt the key
        try:
            encrypted_key = download_encrypted_key(input_bucket, key_object_name)
            decrypted_key = decrypt_key(encrypted_key, kms_key_name)
            
            # Log success (but don't log the actual key content for security)
            log_message("INFO", "Successfully retrieved and decrypted the key", 
                       key_length=len(decrypted_key))
            
            # For demonstration, print the first few characters of the key
            key_preview = decrypted_key[:10].decode('utf-8') + "..." if len(decrypted_key) > 10 else decrypted_key.decode('utf-8')
            log_message("INFO", f"Key preview: {key_preview}")
            
            key_retrieved = True
        except Exception as e:
            log_message("ERROR", f"Failed to retrieve or decrypt key: {str(e)}")
            key_retrieved = False
        
        # Start the Flask web server
        log_message("INFO", "Starting web server on port 8080")
        app.run(host='0.0.0.0', port=8080)
            
    except Exception as e:
        error_message = f"Application failed: {str(e)}"
        log_message("ERROR", error_message, traceback=str(e))
        # Sleep for a short time to ensure logs are flushed before container exits
        time.sleep(5)
        sys.exit(1)

if __name__ == "__main__":
    main() 