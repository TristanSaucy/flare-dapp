"""
EVM Routes Module
This module provides Flask routes for EVM-related functionality.
"""

from flask import Blueprint, jsonify, request
from evm.connection import get_evm_connection, initialize_evm_connection

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
            return jsonify({
                'address': address,
                'balance': balance,
                'symbol': 'ETH'  # This could be different based on the network
            })
        else:
            return jsonify({'error': 'Failed to get ETH balance'}), 400

def register_evm_routes(app):
    """Register EVM routes with the Flask app"""
    app.register_blueprint(evm_bp) 