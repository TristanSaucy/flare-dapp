"""
Gemini AI client for the Confidential Space application.
"""
import os
from google.cloud import aiplatform
from vertexai.preview.generative_models import (
    GenerativeModel, 
    GenerationConfig,
    Content,
    Part,
    FunctionDeclaration,
    Tool,
    AutomaticFunctionCallingResponder
)
from utils.metadata_utils import get_metadata, get_env_var

# Sample Ethereum functions that will be exposed to the model
def get_eth_balance(address: str):
    """
    Get the Ethereum balance for a given address.
    
    Args:
        address: The Ethereum address to check
        
    Returns:
        A dictionary containing the address and its balance
    """
    # This is a mock implementation - in production, you would use web3.py to get the actual balance
    # In your real implementation, you could use:
    # from web3 import Web3
    # from evm.connection import get_evm_connection
    # web3 = get_evm_connection().web3
    # balance = web3.eth.get_balance(address)
    # return {"address": address, "balance": web3.from_wei(balance, 'ether'), "unit": "ETH"}
    
    # Mock implementation for demonstration
    return {
        "address": address,
        "balance": "10.5",
        "unit": "ETH"
    }

def estimate_gas_fee(from_address: str, to_address: str, value: str = "0"):
    """
    Estimate the gas fee for a transaction.
    
    Args:
        from_address: The sender's Ethereum address
        to_address: The recipient's Ethereum address
        value: The amount of ETH to send (in ether)
        
    Returns:
        A dictionary containing the estimated gas fee
    """
    # Mock implementation for demonstration
    return {
        "from": from_address,
        "to": to_address,
        "value": value,
        "estimated_gas": "0.002",
        "unit": "ETH",
        "gas_price": "50",
        "unit_price": "gwei"
    }

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
        
        # Create function declarations from our Ethereum functions
        eth_balance_func = FunctionDeclaration.from_func(get_eth_balance)
        gas_estimate_func = FunctionDeclaration.from_func(estimate_gas_fee)
        
        # Create a tool that groups related functions
        ethereum_tool = Tool(
            function_declarations=[eth_balance_func, gas_estimate_func],
        )
        
        # Create the model instance with tools
        model = GenerativeModel(
            "gemini-2.0-pro-exp-02-05",  # Use the experimental Gemini 2.0 Pro model
            tools=[ethereum_tool],
            system_instruction="You are a helpful assistant that can provide information about the Flare blockchain ecosystem. You can check balances and estimate gas fees."
        )
        
        # Define generation config (will be used when generating content)
        generation_config = GenerationConfig(
            temperature=0.7,
            max_output_tokens=1024,
            top_p=0.95,
            top_k=40
        )
        
        # Set up automatic function calling
        afc_responder = AutomaticFunctionCallingResponder(
            max_automatic_function_calls=3,
        )
        
        # Start a chat session with the responder
        chat = model.start_chat(responder=afc_responder)
        
        # Store the project, location, model, chat session and generation config
        gemini_model = {
            "project_id": project_id,
            "location": location,
            "model": model,
            "chat": chat,
            "generation_config": generation_config,
            "tools": [ethereum_tool],
            "responder": afc_responder,
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
            responder = gemini_model_config.get("responder")
            
            if not model:
                # Recreate the model with tools if needed
                tools = gemini_model_config.get("tools", [])
                model = GenerativeModel(
                    "gemini-2.0-pro-exp-02-05",
                    tools=tools,
                    system_instruction="You are a helpful assistant that can provide information about Ethereum blockchain. You can check balances and estimate gas fees."
                )
                gemini_model_config["model"] = model
            
            # Create a new chat session with the responder for function calling
            if responder:
                chat = model.start_chat(responder=responder)
            else:
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
                responder = gemini_model_config.get("responder")
                
                if responder:
                    chat = model.start_chat(responder=responder)
                else:
                    chat = model.start_chat()
                    
                gemini_model_config["chat"] = chat
                return "I had to restart our conversation. How can I help you?"
        except Exception as reset_error:
            print(f"Failed to reset chat session: {str(reset_error)}")
            
        return f"I encountered an error while processing your request. Please try again later or check the application logs for more information." 