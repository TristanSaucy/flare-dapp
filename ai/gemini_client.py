"""
Gemini AI client for the Confidential Space application.
"""
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, GenerationConfig
from utils.metadata_utils import get_metadata, get_env_var

def initialize_gemini():
    """Initialize the Vertex AI client for Gemini."""
    try:
        # Get project ID from environment or metadata
        project_id = get_env_var("PROJECT_ID")
        if not project_id:
            try:
                project_id = get_metadata("PROJECT_ID")
            except Exception:
                try:
                    # Fallback to metadata server project ID
                    project_id = get_metadata("project/project-id")
                except Exception:
                    pass
        
        # Get region from environment or metadata
        location = get_env_var("REGION", "us-central1")
        if location == "us-central1":  # If using default, try metadata
            try:
                metadata_region = get_metadata("REGION")
                if metadata_region:
                    location = metadata_region
            except Exception:
                pass
        
        if not project_id:
            return None
        
        # Initialize Vertex AI
        aiplatform.init(project=project_id, location=location)
        
        # Create the model instance
        model = GenerativeModel("gemini-2.0-pro-exp-02-05")  # Use the experimental Gemini 2.0 Pro model
        
        # Define generation config (will be used when generating content)
        generation_config = GenerationConfig(
            temperature=0.7,
            max_output_tokens=1024,
            top_p=0.95,
            top_k=40
        )
        
        # Start a chat session
        chat = model.start_chat()
        
        # Store the project, location, model, chat session and generation config
        gemini_model = {
            "project_id": project_id,
            "location": location,
            "model": model,
            "chat": chat,
            "generation_config": generation_config,
            "initialized": True
        }
        
        return gemini_model
    except Exception as e:
        print(f"Failed to initialize Gemini: {str(e)}")
        return None

def get_gemini_response(prompt, gemini_model_config):
    """Get a response from Gemini via Vertex AI using an ongoing chat session."""
    try:
        if not gemini_model_config or not gemini_model_config.get("initialized", False):
            return "I'm sorry, but I'm not able to respond right now due to configuration issues. Please check the logs for more information."
        
        # Get the chat session and generation config from the model config
        chat = gemini_model_config.get("chat")
        generation_config = gemini_model_config.get("generation_config")
        
        if not chat:
            # If chat session doesn't exist for some reason, create a new one
            model = gemini_model_config.get("model")
            if not model:
                model = GenerativeModel("gemini-2.0-pro-exp-02-05")
                gemini_model_config["model"] = model
            
            chat = model.start_chat()
            gemini_model_config["chat"] = chat
        
        # Send the message to the ongoing chat session with generation config
        if generation_config:
            response = chat.send_message(prompt, generation_config=generation_config)
        else:
            response = chat.send_message(prompt)
        
        # Extract the text from the response
        response_text = response.text
        return response_text
    except Exception as e:
        error_msg = f"Failed to get Gemini response: {str(e)}"
        print(error_msg)  # Log the error
        
        # If there's an error with the chat session, try to create a new one
        try:
            if gemini_model_config and gemini_model_config.get("model"):
                model = gemini_model_config.get("model")
                chat = model.start_chat()
                gemini_model_config["chat"] = chat
                return "I had to restart our conversation. How can I help you?"
        except Exception as reset_error:
            print(f"Failed to reset chat session: {str(reset_error)}")
            
        return f"I encountered an error while processing your request. Please try again later or check the application logs for more information." 