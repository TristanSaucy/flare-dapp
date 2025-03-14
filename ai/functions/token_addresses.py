"""
Token addresses for the Flare network.
This file contains a dictionary of token addresses that can be used by the AI.
"""

# Dictionary of token addresses on Flare network
TOKEN_ADDRESSES = {
    # Main tokens
    "WFLR": "0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d",
    "USDT": "0x0B38e83B86d491735fEaa0a791F65c2B99535396",
    "USDC": "0xFbDa5F676cB37624f28265A144A48B0d6e87d3b6",
    "JOULE": "0xE6505f92583103AF7ed9974DEC451A7Af4e3A3bE",
    "SFLR": "0x12e605bc104e93B45e1aD99F9e555f659051c2BB",
    "USDX": "0x4A771Cc1a39FDd8AA08B8EA51F7Fd412e73B3d2B",
    "WETH": "0x1502FA4be69d526124D453619276FacCab275d3D",
    
    # Add more tokens as needed
    # "TOKEN_SYMBOL": "TOKEN_ADDRESS",
}

# Dictionary with additional token information (optional)
TOKEN_INFO = {
    "WFLR": {
        "address": "0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d",
        "name": "Wrapped Flare",
        "decimals": 18,
        "is_native_wrapped": True
    },
    "USDT": {
        "address": "0x0B38e83B86d491735fEaa0a791F65c2B99535396",
        "name": "Tether USD",
        "decimals": 6,
        "is_native_wrapped": False
    },
    "USDC": {
        "address": "0xFbDa5F676cB37624f28265A144A48B0d6e87d3b6",
        "name": "USD Coin",
        "decimals": 6,
        "is_native_wrapped": False
    },
    "JOULE": {
        "address": "0xE6505f92583103AF7ed9974DEC451A7Af4e3A3bE",
        "name": "Joule",
        "decimals": 18,
        "is_native_wrapped": False
    },
    "SFLR": {
        "address": "0x12e605bc104e93B45e1aD99F9e555f659051c2BB",
        "name": "Staked Flare",
        "decimals": 18,
        "is_native_wrapped": False
    },
    "USDX": {
        "address": "0x4A771Cc1a39FDd8AA08B8EA51F7Fd412e73B3d2B",
        "name": "USDX",
        "decimals": 6,
        "is_native_wrapped": False
    },
    "WETH": {
        "address": "0x1502FA4be69d526124D453619276FacCab275d3D",
        "name": "Wrapped Ethereum",
        "decimals": 18,
        "is_native_wrapped": False
    },
    # Add more tokens with their info as needed
}

def get_token_address(symbol: str) -> str:
    """
    Get the address for a token symbol.
    
    Args:
        symbol: The token symbol (e.g., 'WFLR', 'USDT')
        
    Returns:
        The token address or None if not found
    """
    return TOKEN_ADDRESSES.get(symbol.upper())

def get_token_info(symbol: str) -> dict:
    """
    Get detailed information for a token symbol.
    
    Args:
        symbol: The token symbol (e.g., 'WFLR', 'USDT')
        
    Returns:
        A dictionary with token information or None if not found
    """
    return TOKEN_INFO.get(symbol.upper())

def get_token_by_address(address: str) -> str:
    """
    Get the token symbol for an address.
    
    Args:
        address: The token address
        
    Returns:
        The token symbol or None if not found
    """
    address = address.lower()
    for symbol, addr in TOKEN_ADDRESSES.items():
        if addr.lower() == address:
            return symbol
    return None 