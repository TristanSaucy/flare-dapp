"""
Key management utilities for the Confidential Space application.
"""
import os
from google.cloud import storage
from google.cloud import kms
from utils.logging_utils import log_message
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

def download_encrypted_key(bucket_name, key_object_name):
    """Download an encrypted key from a GCS bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(key_object_name)
        
        encrypted_key = blob.download_as_bytes()
        return encrypted_key
    except Exception as e:
        error_msg = f"Failed to download encrypted key: {str(e)}"
        raise RuntimeError(error_msg) from e

def decrypt_key(encrypted_key, kms_key_name):
    """Decrypt a key using Cloud KMS."""
    try:
        kms_client = kms.KeyManagementServiceClient()
        
        # Decrypt the key
        decrypt_response = kms_client.decrypt(
            request={
                "name": kms_key_name,
                "ciphertext": encrypted_key,
            }
        )
        
        decrypted_key = decrypt_response.plaintext
        return decrypted_key
    except Exception as e:
        error_msg = f"Failed to decrypt key: {str(e)}"
        raise RuntimeError(error_msg) from e

def get_private_key():
    """
    Get the private key from environment variables.
    
    Returns:
        str: The private key as a string, with 0x prefix if needed.
    """
    # Try to get the key from environment variables
    private_key = os.environ.get('PRIVATE_KEY')
    
    if not private_key:
        raise ValueError("No private key found in environment variables")
    
    # Ensure the private key has the 0x prefix
    if not private_key.startswith('0x'):
        private_key = '0x' + private_key
    
    return private_key 