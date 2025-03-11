"""
Metadata utilities for the Confidential Space application.
"""
import os
import requests

def get_metadata(metadata_key):
    """Get metadata from the Confidential Space VM metadata server."""
    try:
        url = f"http://metadata.google.internal/computeMetadata/v1/instance/attributes/{metadata_key}"
        headers = {"Metadata-Flavor": "Google"}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            value = response.text
            return value
        else:
            return None
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.Timeout:
        return None
    except Exception:
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
            raise ValueError(error_msg)
        value = default
    
    return value 