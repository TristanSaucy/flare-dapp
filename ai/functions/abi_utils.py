import json
import os
from typing import Dict, Any, Optional

# Directory where ABI files are stored
ABI_DIR = os.path.join(os.path.dirname(__file__), 'abis')

# Cache for loaded ABIs to avoid repeated disk reads
_abi_cache: Dict[str, Any] = {}

def load_abi(contract_name: str) -> Dict:
    """
    Load an ABI from a JSON file by contract name or address.
    
    Args:
        contract_name: Name of the contract or its address (e.g., 'erc20' or '0x...')
        
    Returns:
        The ABI as a dictionary
    
    Raises:
        FileNotFoundError: If the ABI file doesn't exist
    """
    # Check if already in cache
    if contract_name in _abi_cache:
        return _abi_cache[contract_name]
    
    # Try to find the file
    if contract_name.startswith('0x'):
        # It's an address, try to load directly
        file_path = os.path.join(ABI_DIR, f"{contract_name}.json")
        if not os.path.exists(file_path):
            # If not found by address, try common names
            raise FileNotFoundError(f"No ABI file found for address {contract_name}")
    else:
        # It's a name, try to load by name
        file_path = os.path.join(ABI_DIR, f"{contract_name}.json")
    
    # Load the ABI
    try:
        with open(file_path, 'r') as f:
            abi = json.load(f)
        
        # Cache it for future use
        _abi_cache[contract_name] = abi
        return abi
    except FileNotFoundError:
        raise FileNotFoundError(f"ABI file not found: {file_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in ABI file: {file_path}")

def get_function_abi(contract_name: str, function_name: str) -> Optional[Dict]:
    """
    Get the ABI for a specific function in a contract.
    
    Args:
        contract_name: Name of the contract or its address
        function_name: Name of the function to find
        
    Returns:
        The function ABI or None if not found
    """
    abi = load_abi(contract_name)
    
    for item in abi:
        if item.get('type') == 'function' and item.get('name') == function_name:
            return item
    
    return None

def get_event_abi(contract_name: str, event_name: str) -> Optional[Dict]:
    """
    Get the ABI for a specific event in a contract.
    
    Args:
        contract_name: Name of the contract or its address
        event_name: Name of the event to find
        
    Returns:
        The event ABI or None if not found
    """
    abi = load_abi(contract_name)
    
    for item in abi:
        if item.get('type') == 'event' and item.get('name') == event_name:
            return item
    
    return None

def list_available_abis() -> list:
    """
    List all available ABI files.
    
    Returns:
        A list of available ABI names (without the .json extension)
    """
    try:
        files = os.listdir(ABI_DIR)
        return [os.path.splitext(f)[0] for f in files if f.endswith('.json')]
    except FileNotFoundError:
        return []

def get_function_signature(contract_name: str, function_name: str) -> str:
    """
    Get the function signature in the format 'functionName(type1,type2,...)'
    
    Args:
        contract_name: Name of the contract or its address
        function_name: Name of the function
        
    Returns:
        The function signature string
    
    Raises:
        ValueError: If the function is not found
    """
    func_abi = get_function_abi(contract_name, function_name)
    if not func_abi:
        raise ValueError(f"Function {function_name} not found in contract {contract_name}")
    
    input_types = [input_param.get('type') for input_param in func_abi.get('inputs', [])]
    return f"{function_name}({','.join(input_types)})"