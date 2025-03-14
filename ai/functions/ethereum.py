"""
Ethereum-related functions for AI function calling.
These functions allow the AI to interact with the Ethereum blockchain.
"""
from web3 import Web3
from decimal import Decimal
import logging
import os
from eth_account import Account
from evm.connection import get_evm_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _get_account_from_private_key(private_key: str = None):
    """
    Get an Ethereum account from a private key.
    
    Args:
        private_key: The private key to use. If None, uses environment variable.
        
    Returns:
        An Account instance and its address.
    """
    try:
        # If no private key is provided, try to get it from environment
        if not private_key:
            private_key = os.environ.get('PRIVATE_KEY')
            if not private_key:
                logger.error("No private key provided and PRIVATE_KEY environment variable not set")
                return None, None
        
        # Ensure private key has 0x prefix
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        # Create account from private key
        account = Account.from_key(private_key)
        address = account.address
        
        logger.info(f"Created account with address: {address}")
        
        return account, address
    except Exception as e:
        logger.error(f"Error creating account from private key: {str(e)}")
        return None, None

def get_eth_balance(address: str):
    """
    Get the Ethereum balance for a given address.
    
    Args:
        address: The Ethereum address to check
        
    Returns:
        A dictionary containing the address and its balance
    """
    try:
        # Validate the address
        if not Web3.is_address(address):
            return {
                "error": f"Invalid Ethereum address: {address}",
                "status": "error"
            }
        
        # Get Web3 connection from the existing EVM connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        web3 = connection.web3
        
        # Get the balance
        balance_wei = web3.eth.get_balance(address)
        balance_eth = web3.from_wei(balance_wei, 'ether')
        
        # Format the balance to 6 decimal places
        formatted_balance = str(round(Decimal(balance_eth), 6))
        
        # Get network information
        network_info = connection.get_connection_status()['network']
        network_name = network_info.get('name', 'Unknown')
        
        logger.info(f"Retrieved balance for {address} on {network_name}: {formatted_balance} ETH")
        
        return {
            "address": address,
            "balance": formatted_balance,
            "balance_wei": str(balance_wei),
            "unit": "ETH",
            "network": network_name,
            "status": "success"
        }
    except Exception as e:
        error_msg = f"Error getting balance for {address}: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
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
    try:
        # Validate addresses
        if not Web3.is_address(from_address):
            return {
                "error": f"Invalid sender address: {from_address}",
                "status": "error"
            }
        
        if not Web3.is_address(to_address):
            return {
                "error": f"Invalid recipient address: {to_address}",
                "status": "error"
            }
        
        # Get Web3 connection from the existing EVM connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        web3 = connection.web3
        
        # Convert value from ETH to Wei
        try:
            value_wei = web3.to_wei(value, 'ether')
        except ValueError:
            return {
                "error": f"Invalid ETH value: {value}",
                "status": "error"
            }
        
        # Create transaction object for gas estimation
        tx = {
            'from': from_address,
            'to': to_address,
            'value': value_wei,
        }
        
        # Estimate gas
        try:
            gas_estimate = web3.eth.estimate_gas(tx)
        except Exception as e:
            return {
                "error": f"Gas estimation failed: {str(e)}",
                "status": "error"
            }
        
        # Get current gas price
        gas_price = web3.eth.gas_price
        
        # Calculate total gas cost
        gas_cost_wei = gas_estimate * gas_price
        gas_cost_eth = web3.from_wei(gas_cost_wei, 'ether')
        gas_price_gwei = web3.from_wei(gas_price, 'gwei')
        
        # Get network information
        network_info = connection.get_connection_status()['network']
        network_name = network_info.get('name', 'Unknown')
        
        logger.info(f"Estimated gas for transaction from {from_address} to {to_address} on {network_name}: {gas_estimate} units")
        
        return {
            "from": from_address,
            "to": to_address,
            "value": value,
            "value_wei": str(value_wei),
            "gas_units": str(gas_estimate),
            "gas_price": str(round(Decimal(gas_price_gwei), 2)),
            "gas_price_wei": str(gas_price),
            "unit_price": "gwei",
            "total_gas_cost": str(round(Decimal(gas_cost_eth), 6)),
            "total_gas_cost_wei": str(gas_cost_wei),
            "unit": "ETH",
            "network": network_name,
            "status": "success"
        }
    except Exception as e:
        error_msg = f"Error estimating gas fee: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def send_transaction(to_address: str, value: str, private_key: str = None):
    """
    Send an Ethereum transaction.
    
    Args:
        to_address: The recipient's Ethereum address
        value: The amount of ETH to send (in ether)
        private_key: The private key to sign the transaction with. If None, uses environment variable.
        
    Returns:
        A dictionary containing the transaction hash and status
    """
    try:
        # Get account from private key
        account, from_address = _get_account_from_private_key(private_key)
        if not account:
            return {
                "error": "Failed to get account from private key",
                "status": "error"
            }
        
        # Validate recipient address
        if not Web3.is_address(to_address):
            return {
                "error": f"Invalid recipient address: {to_address}",
                "status": "error"
            }
        
        # Get Web3 connection from the existing EVM connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        web3 = connection.web3
        
        # Convert value from ETH to Wei
        try:
            value_wei = web3.to_wei(value, 'ether')
        except ValueError:
            return {
                "error": f"Invalid ETH value: {value}",
                "status": "error"
            }
        
        # Check if the sender has enough balance
        balance_wei = web3.eth.get_balance(from_address)
        gas_price = web3.eth.gas_price
        gas_limit = 21000  # Standard gas limit for ETH transfers
        
        # Calculate total cost (value + gas)
        total_cost_wei = value_wei + (gas_limit * gas_price)
        
        if balance_wei < total_cost_wei:
            balance_eth = web3.from_wei(balance_wei, 'ether')
            total_cost_eth = web3.from_wei(total_cost_wei, 'ether')
            return {
                "error": f"Insufficient funds. You have {balance_eth} ETH but need {total_cost_eth} ETH (including gas) for this transaction.",
                "status": "error"
            }
        
        # Get the nonce for the sender address
        nonce = web3.eth.get_transaction_count(from_address)
        
        # Get network information
        network_info = connection.get_connection_status()['network']
        network_name = network_info.get('name', 'Unknown')
        
        # Create transaction dictionary
        tx = {
            'from': from_address,
            'to': to_address,
            'value': value_wei,
            'nonce': nonce,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'chainId': web3.eth.chain_id
        }
        
        # Sign the transaction
        signed_tx = web3.eth.account.sign_transaction(tx, private_key=account.key.hex())
        
        # Debug logging
        logger.info(f"Signed transaction: {type(signed_tx)}")
        logger.info(f"Signed transaction attributes: {dir(signed_tx)}")
        
        # Send the transaction - use the correct attribute based on Web3.py version
        if hasattr(signed_tx, 'rawTransaction'):
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
        else:
            # For newer Web3.py versions
            tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        tx_hash_hex = web3.to_hex(tx_hash)
        
        logger.info(f"Transaction sent on {network_name}: {tx_hash_hex}")
        
        return {
            "from": from_address,
            "to": to_address,
            "value": value,
            "value_wei": str(value_wei),
            "transaction_hash": tx_hash_hex,
            "network": network_name,
            "status": "success"
        }
    except Exception as e:
        error_msg = f"Error sending transaction: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_transaction_status(tx_hash: str):
    """
    Get the status of an Ethereum transaction.
    
    Args:
        tx_hash: The transaction hash to check
        
    Returns:
        A dictionary containing the transaction status and details
    """
    try:
        # Get Web3 connection from the existing EVM connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        web3 = connection.web3
        
        # Ensure tx_hash has 0x prefix
        if not tx_hash.startswith('0x'):
            tx_hash = '0x' + tx_hash
        
        # Get network information
        network_info = connection.get_connection_status()['network']
        network_name = network_info.get('name', 'Unknown')
        
        # Get the transaction
        try:
            tx = web3.eth.get_transaction(tx_hash)
            if not tx:
                return {
                    "error": f"Transaction not found: {tx_hash}",
                    "status": "error"
                }
        except Exception as e:
            return {
                "error": f"Error retrieving transaction: {str(e)}",
                "status": "error"
            }
        
        # Get transaction receipt to check status
        try:
            receipt = web3.eth.get_transaction_receipt(tx_hash)
            if receipt:
                status = "confirmed" if receipt.status == 1 else "failed"
                block_number = receipt.blockNumber
                gas_used = receipt.gasUsed
            else:
                status = "pending"
                block_number = None
                gas_used = None
        except Exception:
            # Transaction is still pending
            status = "pending"
            block_number = None
            gas_used = None
        
        result = {
            "transaction_hash": tx_hash,
            "from": tx["from"],
            "to": tx["to"],
            "value": str(web3.from_wei(tx["value"], 'ether')),
            "value_wei": str(tx["value"]),
            "status": status,
            "network": network_name,
        }
        
        if block_number is not None:
            result["block_number"] = block_number
        
        if gas_used is not None:
            result["gas_used"] = gas_used
        
        logger.info(f"Transaction {tx_hash} status on {network_name}: {status}")
        
        return result
    except Exception as e:
        error_msg = f"Error checking transaction status: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_network_info():
    """
    Get information about the connected network.
    
    Returns:
        A dictionary containing network information
    """
    try:
        # Get Web3 connection from the existing EVM connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        # Get network information
        network_info = connection.get_connection_status()
        
        return {
            "network": network_info['network']['name'],
            "chain_id": network_info['network']['chain_id'],
            "latest_block": network_info['network']['latest_block'],
            "gas_price": str(Web3.from_wei(network_info['network']['gas_price'], 'gwei')) + " gwei",
            "connected": network_info['connected'],
            "status": "success"
        }
    except Exception as e:
        error_msg = f"Error getting network information: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_my_address():
    """
    Get the Ethereum address associated with the current user using the private key 
    from the environment variable.
    
    Returns:
        A dictionary containing the user's Ethereum address and network information
    """
    try:
        # Get account from private key in environment variable
        account, address = _get_account_from_private_key()
        if not account:
            return {
                "error": "No private key found in environment. Please set the PRIVATE_KEY environment variable.",
                "status": "error"
            }
        
        # Get Web3 connection from the existing EVM connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        # Get network information
        network_info = connection.get_connection_status()['network']
        network_name = network_info.get('name', 'Unknown')
        
        # Get the balance
        balance = get_eth_balance(address)
        
        logger.info(f"Retrieved user address on {network_name}: {address}")
        
        return {
            "address": address,
            "network": network_name,
            "balance": balance.get("balance") if balance.get("status") == "success" else "Unknown",
            "unit": "ETH",
            "status": "success"
        }
    except Exception as e:
        error_msg = f"Error getting user address: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        } 