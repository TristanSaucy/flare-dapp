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
import threading
import datetime
from collections import deque
import google.cloud.logging
from flask import Flask, render_template, request, jsonify, session
from vertexai.generative_models import GenerationConfig

# Import from our modules
from utils.logging_utils import setup_logging, log_message
from utils.metadata_utils import get_metadata, get_env_var
from security.key_management import download_encrypted_key, decrypt_key
from ai.gemini_client import initialize_gemini, get_gemini_response
from evm.connection import initialize_evm_connection, get_evm_connection
from evm.routes import register_evm_routes

# Create Flask app
app = Flask(__name__)

# Configure Flask app with session support
app.secret_key = os.urandom(24)  # Generate a random secret key for sessions

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
evm_connection = None

# Set up logging
logger, cloud_logger, USE_CLOUD_LOGGING = setup_logging()

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
    # Get EVM connection status
    evm_status = get_evm_connection().get_connection_status() if evm_connection else {'connected': False}
    
    return render_template('index.html', 
                          key_retrieved=key_retrieved,
                          uptime=get_uptime(),
                          heartbeat_count=heartbeat_count,
                          input_bucket=config['input_bucket'],
                          key_object=config['key_object'],
                          project_id=config['project_id'],
                          evm_connected=evm_status['connected'],
                          logs=list(recent_logs))

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    """Handle the chat interface with persistent conversation history."""
    # Initialize chat history in session if it doesn't exist
    if 'chat_history' not in session:
        session['chat_history'] = []
    
    # Get EVM connection status for the template
    evm_status = get_evm_connection().get_connection_status() if evm_connection else {'connected': False}
    
    if request.method == 'POST':
        # Handle AJAX request
        if request.is_json:
            data = request.get_json()
            user_input = data.get('user_input', '')
            
            if not user_input:
                return jsonify({'error': 'No input provided'})
            
            # Add user message to chat history
            session['chat_history'].append({'role': 'user', 'content': user_input})
            
            # Get response from Gemini
            response = get_gemini_response(user_input, gemini_model)
            
            # Add assistant response to chat history
            session['chat_history'].append({'role': 'assistant', 'content': response})
            session.modified = True  # Ensure session is saved
            
            return jsonify({
                'response': response,
                'history': session['chat_history'],
                'evm_status': evm_status
            })
        
        # Handle form submission (fallback)
        user_input = request.form.get('user_input', '')
        if not user_input:
            return render_template('chat.html', error='No input provided', history=session['chat_history'], evm_status=evm_status)
        
        # Add user message to chat history
        session['chat_history'].append({'role': 'user', 'content': user_input})
        
        # Get response from Gemini
        response = get_gemini_response(user_input, gemini_model)
        
        # Add assistant response to chat history
        session['chat_history'].append({'role': 'assistant', 'content': response})
        session.modified = True  # Ensure session is saved
        
        return render_template('chat.html', history=session['chat_history'], evm_status=evm_status)
    
    # GET request - just show the chat interface with history
    return render_template('chat.html', history=session.get('chat_history', []), evm_status=evm_status)

@app.route('/reset_chat', methods=['POST'])
def reset_chat():
    """Reset the chat history and start a new conversation."""
    # Clear the chat history in the session
    session['chat_history'] = []
    
    # Reset the Gemini chat session
    if gemini_model and gemini_model.get("model"):
        try:
            # Create a new chat session
            model = gemini_model.get("model")
            chat = model.start_chat()
            gemini_model["chat"] = chat
        except Exception as e:
            log_message("ERROR", f"Failed to reset chat session: {str(e)}", recent_logs=recent_logs,
                      logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
    
    return jsonify({'success': True, 'message': 'Chat history has been reset'})

def heartbeat_thread():
    """Background thread that logs a heartbeat message periodically."""
    global heartbeat_count
    
    while True:
        heartbeat_count += 1
        message = f"Heartbeat #{heartbeat_count} - Application is running"
        log_message("INFO", message, counter=heartbeat_count, recent_logs=recent_logs, 
                   logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        time.sleep(5)

def main():
    """Main entry point for the application."""
    global key_retrieved, config, decrypted_key, gemini_model, evm_connection
    
    try:
        log_message("INFO", "Starting Confidential Space application", recent_logs=recent_logs,
                   logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        
        # Log metadata availability
        try:
            log_message("INFO", "Checking metadata server availability...", recent_logs=recent_logs,
                       logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
            project_id = get_metadata("project-id")
            if project_id:
                log_message("INFO", f"Metadata server is available. Project ID: {project_id}", recent_logs=recent_logs,
                           logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
                config['project_id'] = project_id
            else:
                log_message("WARNING", "Metadata server is not available or project-id not found", recent_logs=recent_logs,
                           logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        except Exception as e:
            log_message("WARNING", f"Error checking metadata server: {str(e)}", recent_logs=recent_logs,
                       logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        
        # Get configuration from environment variables or metadata
        input_bucket = get_env_var("INPUT_BUCKET_NAME", required=True)
        key_object_name = get_env_var("KEY_OBJECT_NAME", default="encrypted-key.enc")
        kms_key_name = get_env_var("KMS_KEY_NAME", required=True)
        
        config['input_bucket'] = input_bucket
        config['key_object'] = key_object_name
        
        log_message("INFO", f"Using input bucket: {input_bucket}", recent_logs=recent_logs,
                   logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        log_message("INFO", f"Using key object: {key_object_name}", recent_logs=recent_logs,
                   logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        log_message("INFO", f"Using KMS key: {kms_key_name}", recent_logs=recent_logs,
                   logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        
        # Initialize Gemini API
        log_message("INFO", "Initializing Vertex AI for Gemini", recent_logs=recent_logs,
                   logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        gemini_model = initialize_gemini()
        if gemini_model and gemini_model.get("initialized", False):
            log_message("INFO", "Vertex AI for Gemini initialized successfully", recent_logs=recent_logs,
                       logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        else:
            log_message("WARNING", "Failed to initialize Vertex AI for Gemini. Chat functionality may be limited.", 
                       recent_logs=recent_logs, logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        
        # Initialize EVM connection
        log_message("INFO", "Initializing EVM connection", recent_logs=recent_logs,
                   logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        
        # Get EVM RPC URL from environment variable if available
        evm_rpc_url = get_env_var("EVM_RPC_URL", required=False, default="https://coston-api.flare.network/ext/bc/C/rpc")
        evm_network = get_env_var("EVM_NETWORK", default="flare-coston")
        
        evm_connection = initialize_evm_connection(evm_rpc_url, evm_network)
        
        if evm_connection and evm_connection.connected:
            log_message("INFO", f"Successfully connected to EVM network: {evm_connection.network_info['name']}", 
                       recent_logs=recent_logs, logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        else:
            log_message("WARNING", "Failed to connect to EVM network. Crypto functionality may be limited.", 
                       recent_logs=recent_logs, logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        
        # Register EVM routes
        register_evm_routes(app)
        
        # Start the heartbeat thread
        thread = threading.Thread(target=heartbeat_thread, daemon=True)
        thread.start()
        
        # Try to download and decrypt the key
        try:
            encrypted_key = download_encrypted_key(input_bucket, key_object_name)
            decrypted_key = decrypt_key(encrypted_key, kms_key_name)
            
            # Log success (but don't log the actual key content for security)
            log_message("INFO", "Successfully retrieved and decrypted the key", 
                       key_length=len(decrypted_key), recent_logs=recent_logs,
                       logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
            
            # For demonstration, print the first few characters of the key
            key_preview = decrypted_key[:10].decode('utf-8') + "..." if len(decrypted_key) > 10 else decrypted_key.decode('utf-8')
            log_message("INFO", f"Key preview: {key_preview}", recent_logs=recent_logs,
                       logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
            
            key_retrieved = True
        except Exception as e:
            log_message("ERROR", f"Failed to retrieve or decrypt key: {str(e)}", recent_logs=recent_logs,
                       logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
            key_retrieved = False
        
        # Start the Flask web server
        log_message("INFO", "Starting web server on port 8080", recent_logs=recent_logs,
                   logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        app.run(host='0.0.0.0', port=8080)
            
    except Exception as e:
        error_message = f"Application failed: {str(e)}"
        log_message("ERROR", error_message, traceback=str(e), recent_logs=recent_logs,
                   logger=logger, cloud_logger=cloud_logger, use_cloud_logging=USE_CLOUD_LOGGING)
        # Sleep for a short time to ensure logs are flushed before container exits
        time.sleep(5)
        sys.exit(1)

if __name__ == "__main__":
    main() 