"""
EVM Connection Module
This module handles connections to Ethereum Virtual Machine (EVM) compatible blockchains
and provides functions to interact with them.
"""

import os
import json
import time
from web3 import Web3

# Default RPC endpoints for different networks
DEFAULT_NETWORKS = {
    'flare-coston': 'https://coston-api.flare.network/ext/bc/C/rpc',
    'songbird': 'https://songbird-api.flare.network/ext/C/rpc',
    'flare': 'https://flare-api.flare.network/ext/C/rpc',
}

# Default RPC URL to use if none is specified
DEFAULT_RPC_URL = 'https://coston-api.flare.network/ext/bc/C/rpc'

class EVMConnection:
    """Class to manage EVM blockchain connections and interactions"""
    
    def __init__(self, rpc_url=None, network_name=None):
        """
        Initialize the EVM connection
        
        Args:
            rpc_url (str, optional): RPC endpoint URL. If not provided, will use environment variable or default.
            network_name (str, optional): Name of the network to connect to (ethereum, goerli, etc.)
        """
        self.web3 = None
        self.connected = False
        self.network_info = {
            'name': 'Flare Coston',  # Default to Flare Coston
            'chain_id': None,
            'latest_block': None,
            'gas_price': None,
            'connection_time': None
        }
        
        # Determine RPC URL
        if rpc_url:
            self.rpc_url = rpc_url
        elif network_name and network_name.lower() in DEFAULT_NETWORKS:
            self.rpc_url = DEFAULT_NETWORKS[network_name.lower()]
            self.network_info['name'] = network_name.capitalize()
        else:
            # Try to get from environment variable or use Flare Coston as default
            self.rpc_url = os.environ.get('EVM_RPC_URL', DEFAULT_RPC_URL)
            
        # Try to connect
        self.connect()
    
    def connect(self):
        """Establish connection to the EVM blockchain"""
        try:
            start_time = time.time()
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            
            # Check connection
            if self.web3.is_connected():
                self.connected = True
                self.network_info['connection_time'] = time.time() - start_time
                
                # Get network information
                try:
                    self.network_info['chain_id'] = self.web3.eth.chain_id
                    self.network_info['latest_block'] = self.web3.eth.block_number
                    self.network_info['gas_price'] = self.web3.eth.gas_price
                    
                    # Try to determine network name from chain ID if not already set
                    if self.network_info['name'] == 'Unknown':
                        chain_id_to_name = {
                            16: 'Flare Coston',  # Flare Coston chain ID
                            19: 'Songbird',      # Songbird chain ID
                            14: 'Flare',         # Flare chain ID
                        }
                        self.network_info['name'] = chain_id_to_name.get(
                            self.network_info['chain_id'], 'Unknown'
                        )
                except Exception as e:
                    print(f"Error getting network info: {str(e)}")
                
                return True
            else:
                self.connected = False
                return False
        except Exception as e:
            self.connected = False
            print(f"Connection error: {str(e)}")
            return False
    
    def get_connection_status(self):
        """Get the current connection status and network information"""
        # Update latest block and gas price if connected
        if self.connected and self.web3:
            try:
                self.network_info['latest_block'] = self.web3.eth.block_number
                self.network_info['gas_price'] = self.web3.eth.gas_price
            except Exception:
                # If we can't get the latest info, we might have lost connection
                self.connected = self.web3.is_connected()
        
        return {
            'connected': self.connected,
            'network': self.network_info
        }
    
    def get_eth_balance(self, address):
        """Get ETH balance for an address"""
        if not self.connected or not self.web3:
            return None
        
        try:
            balance_wei = self.web3.eth.get_balance(address)
            balance_eth = self.web3.from_wei(balance_wei, 'ether')
            return float(balance_eth)
        except Exception as e:
            print(f"Error getting balance: {str(e)}")
            return None
    
    def get_token_balance(self, token_address, wallet_address):
        """Get ERC20 token balance for an address"""
        if not self.connected or not self.web3:
            return None
        
        # Standard ERC20 ABI for balanceOf function
        abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function"
            }
        ]
        
        try:
            # Create contract instance
            token_contract = self.web3.eth.contract(address=token_address, abi=abi)
            
            # Get token decimals and symbol
            decimals = token_contract.functions.decimals().call()
            symbol = token_contract.functions.symbol().call()
            
            # Get raw balance
            raw_balance = token_contract.functions.balanceOf(wallet_address).call()
            
            # Convert to token units
            balance = raw_balance / (10 ** decimals)
            
            return {
                'balance': balance,
                'symbol': symbol,
                'decimals': decimals
            }
        except Exception as e:
            print(f"Error getting token balance: {str(e)}")
            return None

# Global instance that can be imported and used throughout the application
evm_connection = None

def initialize_evm_connection(rpc_url=None, network_name=None):
    """Initialize the global EVM connection"""
    global evm_connection
    evm_connection = EVMConnection(rpc_url, network_name)
    return evm_connection

def get_evm_connection():
    """Get the global EVM connection instance, initializing if needed"""
    global evm_connection
    if evm_connection is None:
        evm_connection = initialize_evm_connection()
    return evm_connection 