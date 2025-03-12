"""
EVM Package
This package provides functionality for interacting with EVM-compatible blockchains.
"""

from evm.connection import initialize_evm_connection, get_evm_connection, EVMConnection

__all__ = ['initialize_evm_connection', 'get_evm_connection', 'EVMConnection'] 