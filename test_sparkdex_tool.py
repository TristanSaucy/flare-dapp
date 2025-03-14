#!/usr/bin/env python3
"""
Test script for SparkDEX tool in Gemini client.
This script demonstrates how the SparkDEX tool works with risk assessment and transaction confirmation.
"""
import os
import sys
import time
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Load environment variables from .env file
load_dotenv()

# Import our Gemini client
from ai.gemini_client import initialize_gemini, get_gemini_response

def main():
    """Main function to test SparkDEX tool with risk assessment"""
    print("Initializing Gemini client with SparkDEX tool...")
    
    # Initialize the Gemini client
    gemini_model = initialize_gemini()
    
    if not gemini_model or not gemini_model.get("initialized", False):
        print("Failed to initialize Gemini client. Check the logs for more information.")
        return
    
    print("Gemini client initialized successfully!")
    print(f"Project ID: {gemini_model.get('project_id')}")
    print(f"Location: {gemini_model.get('location')}")
    
    # Test queries that should trigger risk assessment and transaction confirmation
    test_queries = [
        "Tell me about SparkDEX",
        "What is impermanent loss?",
        "How do I swap tokens on SparkDEX?",
        "I want to provide liquidity to a pool",
        "Swap 10 WFLR for USDC"
    ]
    
    for query in test_queries:
        print("\n" + "="*50)
        print(f"Testing query: {query}")
        print("="*50)
        
        # Get response from Gemini
        start_time = time.time()
        response = get_gemini_response(query, gemini_model)
        end_time = time.time()
        
        # Print response
        print(f"\nGemini response:\n{response}")
        print(f"\n(Response time: {end_time - start_time:.2f} seconds)")
        
        # Wait for user to press Enter before continuing
        input("\nPress Enter to continue to the next query...")
    
    print("\nTest completed. Starting interactive mode. Type 'exit' to quit.")
    
    # Interactive mode
    while True:
        # Get user input
        user_input = input("\nYou: ")
        
        # Check if user wants to exit
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Exiting. Goodbye!")
            break
        
        # Get response from Gemini
        print("\nProcessing...")
        start_time = time.time()
        response = get_gemini_response(user_input, gemini_model)
        end_time = time.time()
        
        # Print response
        print(f"\nGemini: {response}")
        print(f"\n(Response time: {end_time - start_time:.2f} seconds)")

if __name__ == "__main__":
    main() 