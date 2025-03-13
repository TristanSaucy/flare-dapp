"""
EVM Routes Module
This module provides Flask routes for EVM-related functionality.
"""

from flask import Blueprint, jsonify, request, session
from evm.connection import get_evm_connection, initialize_evm_connection
import sys

# Create a Blueprint for EVM routes
evm_bp = Blueprint('evm', __name__)

@evm_bp.route('/api/evm/status', methods=['GET'])
def evm_status():
    """Get the current EVM connection status"""
    evm_conn = get_evm_connection()
    return jsonify(evm_conn.get_connection_status())

@evm_bp.route('/api/evm/connect', methods=['POST'])
def evm_connect():
    """Connect to an EVM network"""
    data = request.get_json()
    rpc_url = data.get('rpc_url')
    network_name = data.get('network_name')
    
    # Initialize a new connection
    evm_conn = initialize_evm_connection(rpc_url, network_name)
    
    return jsonify({
        'success': evm_conn.connected,
        'status': evm_conn.get_connection_status()
    })

@evm_bp.route('/api/evm/balance', methods=['GET'])
def get_balance():
    """Get the balance for an Ethereum address"""
    address = request.args.get('address')
    token_address = request.args.get('token_address')
    
    if not address:
        return jsonify({'error': 'Address is required'}), 400
    
    evm_conn = get_evm_connection()
    
    if not evm_conn.connected:
        return jsonify({'error': 'Not connected to any EVM network'}), 400
    
    if token_address:
        # Get ERC20 token balance
        balance_info = evm_conn.get_token_balance(token_address, address)
        if balance_info:
            return jsonify({
                'address': address,
                'token_address': token_address,
                'balance': balance_info['balance'],
                'symbol': balance_info['symbol']
            })
        else:
            return jsonify({'error': 'Failed to get token balance'}), 400
    else:
        # Get native token (ETH) balance
        balance = evm_conn.get_eth_balance(address)
        if balance is not None:
            # Get the network symbol
            network_name = evm_conn.network_info['name'].lower()
            symbol = 'FLR' if network_name == 'flare' else 'SGB' if network_name == 'songbird' else 'CFLR' if network_name == 'flare coston' else 'ETH'
            
            return jsonify({
                'address': address,
                'balance': balance,
                'symbol': symbol
            })
        else:
            return jsonify({'error': 'Failed to get ETH balance'}), 400

@evm_bp.route('/api/key/address', methods=['GET'])
def get_key_address():
    """Get the Ethereum address derived from the currently loaded private key"""
    try:
        # Import here to avoid circular imports
        from main import log_message, recent_logs, logger, cloud_logger, USE_CLOUD_LOGGING
        from security.key_management import get_private_key
        
        log_message("INFO", "Attempting to derive address from key", 
                   recent_logs=recent_logs, logger=logger, cloud_logger=cloud_logger, 
                   use_cloud_logging=USE_CLOUD_LOGGING)
        
        try:
            # Get the private key from environment variables
            private_key = get_private_key()
            log_message("INFO", f"Retrieved private key from environment, length: {len(private_key)}", 
                       recent_logs=recent_logs, logger=logger, cloud_logger=cloud_logger, 
                       use_cloud_logging=USE_CLOUD_LOGGING)
        except ValueError as e:
            log_message("ERROR", f"Failed to get private key: {str(e)}", 
                       recent_logs=recent_logs, logger=logger, cloud_logger=cloud_logger, 
                       use_cloud_logging=USE_CLOUD_LOGGING)
            return jsonify({'error': 'No private key is currently loaded'}), 400
        
        # Import web3 here to avoid circular imports
        from web3 import Web3
        from eth_account import Account
        
        # Log the key length (don't log the actual key)
        log_message("INFO", f"Final private key length: {len(private_key)}", 
                   recent_logs=recent_logs, logger=logger, cloud_logger=cloud_logger, 
                   use_cloud_logging=USE_CLOUD_LOGGING)
        
        # Derive the address from the private key
        try:
            account = Account.from_key(private_key)
            address = account.address
            
            log_message("INFO", f"Successfully derived address: {address}", 
                       recent_logs=recent_logs, logger=logger, cloud_logger=cloud_logger, 
                       use_cloud_logging=USE_CLOUD_LOGGING)
            
            # Clear the account object to avoid keeping the key in memory
            del account
            
            return jsonify({
                'success': True,
                'address': address
            })
        except Exception as inner_e:
            log_message("ERROR", f"Failed to create account from key: {str(inner_e)}", 
                       recent_logs=recent_logs, logger=logger, cloud_logger=cloud_logger, 
                       use_cloud_logging=USE_CLOUD_LOGGING)
            raise inner_e
        
    except Exception as e:
        import logging
        logging.error(f"Failed to derive address from key: {str(e)}")
        return jsonify({'error': f'Failed to derive address: {str(e)}'}), 500

def register_evm_routes(app):
    """Register EVM routes with the Flask app"""
    app.register_blueprint(evm_bp) 