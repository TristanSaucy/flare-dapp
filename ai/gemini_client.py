"""
Gemini AI client for the Confidential Space application.
"""
import os
import logging
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
from ai.functions import available_functions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
        # Create function declarations for all available functions
        function_declarations = []
        for func_name, func in available_functions.items():
            function_declarations.append(FunctionDeclaration.from_func(func))
        
        # Create a single tool that contains all functions
        blockchain_tool = Tool(
            function_declarations=function_declarations,
        )
        
        # Create the model instance with the tool
        model = GenerativeModel(
            "gemini-2.0-pro-exp-02-05",  # Use the experimental Gemini 2.0 Pro model
            tools=[blockchain_tool],
            system_instruction="""You are a helpful assistant that can provide information about the Ethereum blockchain and SparkDEX decentralized exchange on Flare Network.

For Ethereum, you can check balances, estimate gas fees, send transactions, and check transaction status. When the user asks about 'my address' or 'my balance', use the get_my_address function which retrieves their address from the environment variable.

For SparkDEX, you can provide information about pools, tokens, prices, and liquidity positions. When discussing SparkDEX, always include the following guidance:

1. Risk Assessment: Always inform users about the risks of decentralized finance, including smart contract risks, impermanent loss in liquidity pools, and price volatility.

2. Transaction Confirmation: NEVER execute any transaction (swap, liquidity provision, etc.) without explicit confirmation from the user. Always present the details of the transaction and ask for confirmation before proceeding.

3. Educational Guidance: Provide educational context when users ask about complex DeFi concepts like impermanent loss, slippage, or price impact.

4. Fee Awareness: Always mention the applicable fees for any operation on SparkDEX, including swap fees, gas costs, and any other relevant costs.

5. Security Best Practices: Remind users about security best practices when interacting with DeFi protocols, such as checking contract addresses and starting with small amounts for unfamiliar operations.

When handling any transaction that involves user funds, you must:
- Present all relevant details of the transaction
- Clearly state the risks involved
- Ask for explicit confirmation
- Provide an option to cancel
- Never proceed without clear user approval"""
        )
        
        # Define generation config (will be used when generating content)
        generation_config = GenerationConfig(
            temperature=0.2,  # Lower temperature for more deterministic responses
            max_output_tokens=1024,
            top_p=0.95,
            top_k=40
        )
        
        # Set up automatic function calling
        afc_responder = AutomaticFunctionCallingResponder(
            max_automatic_function_calls=20,
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
            "tools": [blockchain_tool],
            "responder": afc_responder,
            "initialized": True
        }
        
        logger.info(f"Gemini model initialized successfully with {len(function_declarations)} blockchain functions")
        
        return gemini_model
    except Exception as e:
        logger.error(f"Failed to initialize Gemini: {str(e)}")
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
                    system_instruction="""You are a helpful assistant that can provide information about Ethereum blockchain and SparkDEX decentralized exchange. You can check balances, estimate gas fees, send transactions, and check transaction status. For SparkDEX operations, always provide risk assessments and require explicit user confirmation before executing any transactions."""
                )
                gemini_model_config["model"] = model
            
            # Create a new chat session with the responder for function calling
            if responder:
                chat = model.start_chat(responder=responder)
            else:
                chat = model.start_chat()
                
            gemini_model_config["chat"] = chat
            logger.info("Created new chat session")
        
        # Log the user query
        logger.info(f"User query: {prompt}")
        
        # Send the message to the ongoing chat session with generation config
        if generation_config:
            response = chat.send_message(prompt, generation_config=generation_config)
        else:
            response = chat.send_message(prompt)
        
        # Extract the text from the response
        response_text = response.text
        logger.info(f"Generated response of length {len(response_text)}")
        
        return response_text
    except Exception as e:
        error_msg = f"Failed to get Gemini response: {str(e)}"
        logger.error(error_msg)
        
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
                logger.info("Restarted chat session after error")
                return "I had to restart our conversation. How can I help you?"
        except Exception as reset_error:
            logger.error(f"Failed to reset chat session: {str(reset_error)}")
            
        return f"I encountered an error while processing your request. Please try again later or check the application logs for more information." 