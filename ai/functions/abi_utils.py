import json
import os
from typing import Dict, Any, Optional

# Directory where ABI files are stored
ABI_DIR = os.path.join(os.path.dirname(__file__), 'abis')

# Mapping of contract addresses to ABI names
# This allows us to use descriptive ABI filenames instead of address-based filenames
CONTRACT_ABI_MAPPING = {
    # SparkDEX contracts
    "0x8a1E35F5c98C4E85B36B7B253222eE17773b2781": "swap_router_abi",  # SwapRouter
    "0x5B5513c55fd06e2658010c121c37b07fC8e8B705": "quoter_v2_abi",    # QuoterV2
    "0x8A2578d23d4C532cC9A98FaD91C0523f5efDE652": "v3_factory_abi",   # V3Factory
    
    # Token contracts
    "0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d": "erc20",           # WFLR
    "0x0B38e83B86d491735fEaa0a791F65c2B99535396": "erc20",           # USDT
    "0xFbDa5F676cB37624f28265A144A48B0d6e87d3b6": "erc20",           # USDC
    "0xE6505f92583103AF7ed9974DEC451A7Af4e3A3bE": "erc20",           # JOULE
    "0x12e605bc104e93B45e1aD99F9e555f659051c2BB": "erc20",           # SFLR
    "0x4A771Cc1a39FDd8AA08B8EA51F7Fd412e73B3d2B": "erc20",           # USDX
    "0x1502FA4be69d526124D453619276FacCab275d3D": "erc20",           # WETH
    
    # Add more mappings as needed
}

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
        # It's an address, check if we have a mapping for it
        if contract_name in CONTRACT_ABI_MAPPING:
            # Use the mapped ABI name
            abi_name = CONTRACT_ABI_MAPPING[contract_name]
            file_path = os.path.join(ABI_DIR, f"{abi_name}.json")
        else:
            # Try to load directly by address
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

def add_token_to_abi_mapping(token_address: str, abi_name: str = "erc20") -> bool:
    """
    Add a token address to the CONTRACT_ABI_MAPPING dictionary.
    
    Args:
        token_address: The token address to add
        abi_name: The ABI name to map to (default: "erc20")
        
    Returns:
        True if the token was added, False if it was already in the mapping
    """
    global CONTRACT_ABI_MAPPING
    
    if token_address in CONTRACT_ABI_MAPPING:
        return False
    
    CONTRACT_ABI_MAPPING[token_address] = abi_name
    return True