"""
SparkDEX-related functions for AI function calling.
These functions allow the AI to interact with SparkDEX contracts on the Flare network.
"""
import os
import json
import logging
import requests
from web3 import Web3
from decimal import Decimal
from eth_account import Account
from evm.connection import get_evm_connection
from .abi_utils import load_abi, get_function_abi, get_event_abi
from web3.middleware import ExtraDataToPOAMiddleware
import time
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SparkDEX contract addresses
SPARKDEX_CONTRACTS = {
    # V3.1 DEX
    "v3Factory": "0x8A2578d23d4C532cC9A98FaD91C0523f5efDE652",
    "swapRouter": "0x8a1E35F5c98C4E85B36B7B253222eE17773b2781",
    "universalRouter": "0x0f3D8a38D4c74afBebc2c42695642f0e3acb15D3",
    "nonfungiblePositionManager": "0xEE5FF5Bc5F852764b5584d92A4d592A53DC527da",
    "quoterV2": "0x5B5513c55fd06e2658010c121c37b07fC8e8B705",
    
    # V2 DEX
    "v2Factory": "0x16b619B04c961E8f4F06C10B42FDAbb328980A89",
    "uniswapV2Router02": "0x4a1E5A90e9943467FAd1acea1E7F0e5e88472a1e",
    
    # Perps
    "orderBook": "0xE9dD1644Db3726815d528B1dde92dd9c5659873a",
    "positionManager": "0x8ebe8d5F65fEE1B43D64cb9E1935663edb9408Af",
    "fundingTracker": "0xC03cD72b17d5eD82397d26e78be6CcE3184d8978"
}

def _get_account_from_private_key(private_key=None):
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

def _get_contract_abi(contract_address):
    """
    Get the ABI for a contract.
    
    Args:
        contract_address: The contract address
        
    Returns:
        The contract ABI as a JSON object
    """
    try:
        # First try to load from our local ABIs
        try:
            return load_abi(contract_address)
        except FileNotFoundError:
            pass
        
        # If not found locally, try to get from Flare Explorer API
        api_url = f"https://api.flarescan.com/api?module=contract&action=getabi&address={contract_address}"
        response = requests.get(api_url)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "1" and result.get("result"):
                return json.loads(result.get("result"))
        
        logger.error(f"No ABI found for contract {contract_address}")
        return None
    except Exception as e:
        logger.error(f"Error getting ABI for {contract_address}: {str(e)}")
        return None

def _get_contract(contract_address, abi=None):
    """
    Get a Web3 contract instance.
    
    Args:
        contract_address: The contract address
        abi: The contract ABI (optional) or ABI name (e.g., "v3_pool_abi")
        
    Returns:
        A Web3 contract instance
    """
    try:
        # Get Web3 connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            logger.error("Failed to connect to Ethereum node")
            return None
        
        web3 = connection.web3
        
        # Add PoA middleware if not already added
        _ensure_poa_middleware(web3)
        
        # Get ABI if not provided
        if not abi:
            abi = _get_contract_abi(contract_address)
            if not abi:
                return None
        elif isinstance(abi, str):
            # If abi is a string, it's an ABI name, so load it
            try:
                abi = load_abi(abi)
                if not abi:
                    logger.error(f"Failed to load ABI: {abi}")
                    return None
            except Exception as e:
                logger.error(f"Error loading ABI {abi}: {str(e)}")
                return None
        
        # Create contract instance
        contract = web3.eth.contract(address=contract_address, abi=abi)
        return contract
    except Exception as e:
        logger.error(f"Error creating contract instance for {contract_address}: {str(e)}")
        return None



def get_sparkdex_info():
    """
    Get general information about SparkDEX contracts.
    
    Returns:
        A dictionary containing information about SparkDEX contracts
    """
    try:
        # Get Web3 connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        # Get network information
        network_info = connection.get_connection_status()['network']
        network_name = network_info.get('name', 'Unknown')
        
        # Return contract addresses
        return {
            "network": network_name,
            "contracts": SPARKDEX_CONTRACTS,
            "status": "success"
        }
    except Exception as e:
        error_msg = f"Error getting SparkDEX info: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_v3_factory_info():
    """
    Get information about the SparkDEX V3 Factory contract.
    
    Returns:
        A dictionary containing information about the V3 Factory
    """
    try:
        factory_address = SPARKDEX_CONTRACTS["v3Factory"]
        factory_contract = _get_contract(factory_address, "v3_factory_abi")
        
        if not factory_contract:
            return {
                "error": f"Failed to get contract instance for {factory_address}",
                "status": "error"
            }
        
        # Get factory information
        try:
            owner = factory_contract.functions.owner().call()
            fee_amount_tickspacing = []
            
            # Common fee tiers in V3
            fee_tiers = [100, 500, 3000, 10000]  # 0.01%, 0.05%, 0.3%, 1%
            
            for fee in fee_tiers:
                try:
                    tickSpacing = factory_contract.functions.feeAmountTickSpacing(fee).call()
                    fee_amount_tickspacing.append({
                        "fee": fee,
                        "tickSpacing": tickSpacing,
                        "feePercent": fee / 10000
                    })
                except Exception:
                    # This fee tier might not be configured
                    pass
            
            return {
                "address": factory_address,
                "owner": owner,
                "feeAmountTickSpacing": fee_amount_tickspacing,
                "status": "success"
            }
        except Exception as e:
            return {
                "error": f"Error calling factory methods: {str(e)}",
                "status": "error"
            }
    except Exception as e:
        error_msg = f"Error getting V3 Factory info: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_pool_info(token0_address: str, token1_address: str, fee: int = 3000):
    """
    Get information about a SparkDEX V3 pool.
    
    Args:
        token0_address: The address of the first token in the pair
        token1_address: The address of the second token in the pair
        fee: The fee tier of the pool (default: 3000 = 0.3%)
        
    Returns:
        A dictionary containing information about the pool
    """
    try:
        # Validate addresses
        if not Web3.is_address(token0_address):
            return {
                "error": f"Invalid token0 address: {token0_address}",
                "status": "error"
            }
        
        if not Web3.is_address(token1_address):
            return {
                "error": f"Invalid token1 address: {token1_address}",
                "status": "error"
            }
        
        # Get factory contract
        factory_address = SPARKDEX_CONTRACTS["v3Factory"]
        factory_contract = _get_contract(factory_address, "v3_factory_abi")
        
        if not factory_contract:
            return {
                "error": f"Failed to get contract instance for {factory_address}",
                "status": "error"
            }
        
        # Get pool address
        try:
            pool_address = factory_contract.functions.getPool(token0_address, token1_address, fee).call()
            
            if pool_address == '0x0000000000000000000000000000000000000000':
                return {
                    "error": f"Pool does not exist for tokens {token0_address} and {token1_address} with fee {fee}",
                    "status": "error"
                }
            
            # Get pool contract
            pool_contract = _get_contract(pool_address, "v3_pool_abi")
            
            if not pool_contract:
                return {
                    "pool_address": pool_address,
                    "message": "Pool exists but could not get contract instance",
                    "status": "partial"
                }
            
            # Get pool information
            token0 = pool_contract.functions.token0().call()
            token1 = pool_contract.functions.token1().call()
            fee_actual = pool_contract.functions.fee().call()
            liquidity = pool_contract.functions.liquidity().call()
            slot0 = pool_contract.functions.slot0().call()
            
            # Format slot0 data
            sqrt_price_x96 = slot0[0]
            tick = slot0[1]
            
            # Calculate price from sqrtPriceX96
            price = (sqrt_price_x96 / (2**96))**2
            
            return {
                "pool_address": pool_address,
                "token0": token0,
                "token1": token1,
                "fee": fee_actual,
                "liquidity": liquidity,
                "sqrtPriceX96": sqrt_price_x96,
                "tick": tick,
                "price": price,
                "status": "success"
            }
        except Exception as e:
            return {
                "error": f"Error getting pool info: {str(e)}",
                "status": "error"
            }
    except Exception as e:
        error_msg = f"Error getting pool info: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_token_price(token_address: str, quote_token_address: str = "0x1D1F1A7280D67246665Bb196F38553b469294f12"):
    """
    Get the price of a token in terms of another token.
    
    Args:
        token_address: The address of the token to get the price for
        quote_token_address: The address of the token to quote the price in (default: USDC)
        
    Returns:
        A dictionary containing the price information
    """
    try:
        # Validate addresses
        if not Web3.is_address(token_address):
            return {
                "error": f"Invalid token address: {token_address}",
                "status": "error"
            }
        
        if not Web3.is_address(quote_token_address):
            return {
                "error": f"Invalid quote token address: {quote_token_address}",
                "status": "error"
            }
        
        # Get quoter contract
        quoter_address = SPARKDEX_CONTRACTS["quoterV2"]
        quoter_contract = _get_contract(quoter_address, "quoter_v2_abi")
        
        if not quoter_contract:
            return {
                "error": f"Failed to get contract instance for {quoter_address}",
                "status": "error"
            }
        
        # Get Web3 connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        web3 = connection.web3
        
        # Amount to quote (1 token with 18 decimals)
        amount_in = 10**18
        
        # Common fee tiers to try
        fee_tiers = [100, 500, 3000, 10000]
        
        for fee in fee_tiers:
            try:
                # Try to get quote
                quote_params = {
                    'tokenIn': token_address,
                    'tokenOut': quote_token_address,
                    'fee': fee,
                    'amountIn': amount_in,
                    'sqrtPriceLimitX96': 0
                }
                
                quote_result = quoter_contract.functions.quoteExactInputSingle(quote_params).call()
                amount_out = quote_result[0]
                
                # Calculate price
                price = amount_out / amount_in
                
                return {
                    "token": token_address,
                    "quote_token": quote_token_address,
                    "price": price,
                    "fee_tier": fee,
                    "status": "success"
                }
            except Exception:
                # Try next fee tier
                continue
        
        # If we get here, we couldn't get a quote for any fee tier
        return {
            "error": f"Could not get price for token {token_address}",
            "status": "error"
        }
    except Exception as e:
        error_msg = f"Error getting token price: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_perp_markets():
    """
    Get information about available perpetual markets on SparkDEX.
    
    Returns:
        A dictionary containing information about perpetual markets
    """
    try:
        # Get position manager contract
        position_manager_address = SPARKDEX_CONTRACTS["positionManager"]
        position_manager_contract = _get_contract(position_manager_address)
        
        if not position_manager_contract:
            return {
                "error": f"Failed to get contract instance for {position_manager_address}",
                "status": "error"
            }
        
        # Try to get markets information
        try:
            # This is a placeholder - actual method depends on the contract implementation
            markets_count = position_manager_contract.functions.marketsCount().call()
            markets = []
            
            for i in range(markets_count):
                market_info = position_manager_contract.functions.getMarketInfo(i).call()
                markets.append({
                    "index": i,
                    "name": market_info[0],
                    "address": market_info[1],
                    "isActive": market_info[2]
                })
            
            return {
                "markets_count": markets_count,
                "markets": markets,
                "status": "success"
            }
        except Exception as e:
            return {
                "error": f"Error getting markets info: {str(e)}",
                "message": "This function may need adjustment based on the actual contract implementation",
                "status": "error"
            }
    except Exception as e:
        error_msg = f"Error getting perpetual markets: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def swap_tokens(token_in_address: str, token_out_address: str, amount_in: str, slippage: float = 0.5, private_key: str = None):
    """
    Swap tokens on SparkDEX.
    
    Args:
        token_in_address: The address of the token to swap from
        token_out_address: The address of the token to swap to
        amount_in: The amount of input tokens to swap
        slippage: The maximum slippage percentage (default: 0.5%)
        private_key: The private key to use for the transaction (default: uses environment variable)
        
    Returns:
        A dictionary containing the transaction details
    """
    try:
        logger.info(f"Starting token swap: {token_in_address} -> {token_out_address}, amount: {amount_in}")
        
        # Validate addresses
        if not Web3.is_address(token_in_address):
            logger.error(f"Invalid input token address: {token_in_address}")
            return {
                "error": f"Invalid input token address: {token_in_address}",
                "status": "error"
            }
        
        if not Web3.is_address(token_out_address):
            logger.error(f"Invalid output token address: {token_out_address}")
            return {
                "error": f"Invalid output token address: {token_out_address}",
                "status": "error"
            }
        
        # Get account from private key
        logger.info("Getting account from private key")
        account, from_address = _get_account_from_private_key(private_key)
        if not account:
            logger.error("Failed to get account from private key")
            return {
                "error": "Failed to get account from private key",
                "status": "error"
            }
        
        # Get Web3 connection
        logger.info("Establishing Web3 connection")
        connection = get_evm_connection()
        if not connection or not connection.connected:
            logger.error("Failed to connect to Ethereum node")
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        web3 = connection.web3
        
        # Ensure PoA middleware is added
        logger.debug("Ensuring PoA middleware is added")
        _ensure_poa_middleware(web3)
        
        # Get router contract
        logger.info(f"Getting router contract at {SPARKDEX_CONTRACTS['swapRouter']}")
        router_address = SPARKDEX_CONTRACTS["swapRouter"]
        router_contract = _get_contract(router_address, "swap_router_abi")
        
        if not router_contract:
            logger.error(f"Failed to get contract instance for {router_address}")
            return {
                "error": f"Failed to get contract instance for {router_address}",
                "status": "error"
            }
        
        # Get token contracts
        logger.info(f"Getting token contract for {token_in_address}")
        token_in_contract = _get_contract(token_in_address)
        if not token_in_contract:
            logger.error(f"Failed to get contract instance for {token_in_address}")
            return {
                "error": f"Failed to get contract instance for {token_in_address}",
                "status": "error"
            }
        
        # Get token decimals
        try:
            logger.info("Getting token decimals")
            decimals = token_in_contract.functions.decimals().call()
            logger.debug(f"Token decimals: {decimals}")
            amount_in_wei = int(float(amount_in) * 10**decimals)
            logger.info(f"Amount in wei: {amount_in_wei}")
        except Exception as e:
            logger.error(f"Error getting token decimals: {str(e)}")
            # Default to 18 decimals if we can't get the actual value
            amount_in_wei = int(float(amount_in) * 10**18)
            logger.info(f"Using default 18 decimals. Amount in wei: {amount_in_wei}")
        
        amount_in_converted = int(amount_in)

        # Check allowance and approve if needed
        try:
            logger.info(f"Checking token allowance for router {router_address}")
            allowance = token_in_contract.functions.allowance(from_address, router_address).call()
            logger.debug(f"Current allowance: {allowance}")
            
            if allowance < amount_in_wei:
                logger.info("Allowance insufficient, approving tokens")
                # Approve router to spend tokens
                approve_tx = token_in_contract.functions.approve(
                    router_address,
                    2**256 - 1  # Max uint256 value
                ).build_transaction({
                    'from': from_address,
                    'nonce': web3.eth.get_transaction_count(from_address),
                    'gas': 100000,
                    'gasPrice': web3.eth.gas_price,
                    'chainId': web3.eth.chain_id
                })
                
                # Sign and send approval transaction using our helper function
                try:
                    logger.info("Signing and sending approval transaction")
                    tx_hash = _sign_and_send_transaction(web3, approve_tx, account)
                    logger.info(f"Approval transaction sent: {tx_hash}")
                    
                    logger.info("Waiting for approval transaction receipt")
                    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
                    logger.info(f"Approval transaction confirmed: status={receipt.status}")
                    
                    if receipt.status != 1:
                        logger.error("Approval transaction failed")
                        return {
                            "error": "Approval transaction failed",
                            "tx_hash": web3.to_hex(tx_hash),
                            "status": "error"
                        }
                except Exception as e:
                    logger.error(f"Error approving tokens: {str(e)}")
                    return {
                        "error": f"Error approving tokens: {str(e)}",
                        "status": "error"
                    }
            else:
                logger.info("Token allowance sufficient, no approval needed")
        except Exception as e:
            logger.error(f"Error checking allowance: {str(e)}")
            return {
                "error": f"Error checking allowance: {str(e)}",
                "status": "error"
            }
        
        # Get quote for minimum amount out
        logger.info("Getting quote for swap")
        quoter_address = SPARKDEX_CONTRACTS["quoterV2"]
        quoter_contract = _get_contract(quoter_address, "quoter_v2_abi")
        
        if not quoter_contract:
            logger.error(f"Failed to get contract instance for {quoter_address}")
            return {
                "error": f"Failed to get contract instance for {quoter_address}",
                "status": "error"
            }
        
        # Default fee tier
        fee = 3000  # 0.3%
        logger.info(f"Using fee tier: {fee} (0.3%)")
        
        # Convert addresses to checksum format
        token_in_checksum = Web3.to_checksum_address(token_in_address)
        token_out_checksum = Web3.to_checksum_address(token_out_address)
        logger.info(f"Converted token addresses to checksum format: {token_in_checksum}, {token_out_checksum}")

        # Try to get quote
        try:
            logger.info("Preparing quote parameters")
            quote_params = {
                'tokenIn': token_in_checksum,
                'tokenOut': token_out_checksum,
                'fee': fee,
                'amountIn': amount_in_wei,
                'sqrtPriceLimitX96': 0
            }
            
            logger.info("Calling quoter contract")
            quote_result = quoter_contract.functions.quoteExactInputSingle(quote_params).call()
            amount_out = quote_result[0]
            logger.info(f"Quote received: expected output amount = {amount_out}")
            
            # Apply slippage
            min_amount_out = int(amount_out * (1 - slippage / 100))
            logger.info(f"Minimum amount out with {slippage}% slippage: {min_amount_out}")
        except Exception as e:
            logger.error(f"Error getting quote: {str(e)}")
            return {
                "error": f"Error getting quote: {str(e)}",
                "status": "error"
            }
        
        # Current timestamp plus 20 minutes
        current_time = int(time.time())
        deadline = current_time + 1200
        logger.info(f"Setting transaction deadline: {deadline} (current time + 20 minutes)")
        
        token_in_bytes = Web3.to_bytes(hexstr=token_in_checksum)
        token_out_bytes = Web3.to_bytes(hexstr=token_out_checksum)
        recipient_checksum = Web3.to_bytes(hexstr=Web3.to_checksum_address(from_address))
        # Build swap transaction
        try:
            logger.info("Building swap transaction")
            recipient_checksum = Web3.to_checksum_address(from_address)
            logger.info(f"Converted recipient address to checksum format: {recipient_checksum}")
            
            swap_params = {
                'tokenIn': token_in_bytes,
                'tokenOut': token_out_bytes,
                'fee': fee,
                'recipient': recipient_checksum,
                'deadline': deadline,
                'amountIn': amount_in_wei,
                'amountOutMinimum': min_amount_out,
                'sqrtPriceLimitX96': 0
            }
            
            logger.info(f"Swap parameters: {swap_params}")
            logger.info("Parameter types:")
            for key, value in swap_params.items():
                logger.info(f"{key}: {value} (type: {type(value)})")
            
            try:
                nonce = web3.eth.get_transaction_count(from_address)
                logger.info(f"Current nonce: {nonce}")
            except Exception as e:
                logger.error(f"Error getting transaction count: {str(e)}")
                return {
                    "error": f"Error getting transaction count: {str(e)}",
                    "status": "error"
                }
            
            try:
                gas_price = web3.eth.gas_price
                logger.info(f"Current gas price: {gas_price}")
            except Exception as e:
                logger.error(f"Error getting gas price: {str(e)}")
                return {
                    "error": f"Error getting gas price: {str(e)}",
                    "status": "error"
                }
            
            try:
                chain_id = web3.eth.chain_id
                logger.info(f"Chain ID: {chain_id}")
            except Exception as e:
                logger.error(f"Error getting chain ID: {str(e)}")
                return {
                    "error": f"Error getting chain ID: {str(e)}",
                    "status": "error"
                }
            
            try:
                # Build transaction with more detailed error handling
                tx_params = {
                    'from': from_address,
                    'nonce': nonce,
                    'gas': 600000,
                    'gasPrice': gas_price,
                    'chainId': chain_id,
                }
                logger.info(f"Transaction parameters: {tx_params}")
                
                # First check if the function exists
                if not hasattr(router_contract.functions, 'exactInputSingle'):
                    logger.error("Router contract does not have exactInputSingle function")
                    return {
                        "error": "Router contract does not have exactInputSingle function",
                        "status": "error"
                    }
                
                # Build the transaction
                swap_tx = router_contract.functions.exactInputSingle(swap_params).build_transaction(tx_params)
                logger.info("Swap transaction built successfully")
            except Exception as e:
                logger.error(f"Error building transaction object: {str(e)}")
                return {
                    "error": f"Error building transaction object: {str(e)}",
                    "status": "error"
                }
            
            # Sign and send swap transaction using our helper function
            logger.info("Starting inline transaction signing process")
            try:
                # Log transaction details
                logger.info(f"Transaction to sign: gas={swap_tx.get('gas')}, nonce={swap_tx.get('nonce')}")
                logger.info(f"Transaction destination: {swap_tx.get('to')}")
                
                # Ensure POA middleware is added
                logger.debug("Ensuring POA middleware is added")
                if ExtraDataToPOAMiddleware not in web3.middleware_onion:
                    web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
                    logger.debug("Added POA middleware")
                
                # Log account details (safely)
                logger.info(f"Signing with account: {account.address}")
                
                # Sign the transaction
                logger.info("Signing transaction...")
                signed_tx = web3.eth.account.sign_transaction(swap_tx, private_key=account.key)
                logger.info("Transaction signed successfully")
                
                # Send the transaction
                logger.info("Sending raw transaction to network...")
                if hasattr(signed_tx, 'raw_transaction'):
                    logger.debug("Using raw_transaction attribute (newer Web3.py)")
                    tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
                elif hasattr(signed_tx, 'rawTransaction'):
                    logger.debug("Using rawTransaction attribute (older Web3.py)")
                    tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                else:
                    error_msg = "Cannot find raw transaction data in signed transaction"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                logger.info(f"Raw transaction sent successfully with hash: {tx_hash.hex()}")
                
                # Don't convert to hex string here - keep the original tx_hash object
                # This should avoid the type conversion issue
                
            except Exception as e:
                error_msg = f"Error in inline transaction signing/sending: {str(e)}"
                logger.error(error_msg)
                
                # Log more details about the transaction that failed
                try:
                    logger.error("Transaction that failed:")
                    for key, value in swap_tx.items():
                        logger.error(f"  {key}: {value}")
                except:
                    logger.error("Could not log transaction details")
                    
                raise Exception(error_msg)
            
            # Now continue with the original code, using tx_hash directly
            logger.info(f"Transaction hash (for logging): {tx_hash.hex()}")
            logger.info(f"Transaction hash type: {type(tx_hash)}")

            # Wait for receipt using the original tx_hash object
            logger.info("Waiting for transaction receipt...")
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info("Swap completed successfully")
            return {
                "transaction_hash": web3.to_hex(tx_hash),
                "from_address": from_address,
                "token_in": token_in_address,
                "token_out": token_out_address,
                "amount_in": amount_in_converted,
                "amount_in_wei": amount_in_wei,
                "expected_amount_out": amount_out,
                "min_amount_out": min_amount_out,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error building swap transaction: {str(e)}")
            return {
                "error": f"Error building swap transaction: {str(e)}",
                "status": "error"
            }
    except Exception as e:
        error_msg = f"Error swapping tokens: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_user_positions():
    """
    Get the user's liquidity positions on SparkDEX.
    
    Returns:
        A dictionary containing the user's positions
    """
    try:
        # Get account from private key
        _, user_address = _get_account_from_private_key()
        if not user_address:
            return {
                "error": "Failed to get account from private key",
                "status": "error"
            }
        
        # Get position manager contract
        nft_manager_address = SPARKDEX_CONTRACTS["nonfungiblePositionManager"]
        nft_manager_contract = _get_contract(nft_manager_address)
        
        if not nft_manager_contract:
            return {
                "error": f"Failed to get contract instance for {nft_manager_address}",
                "status": "error"
            }
        
        # Get Web3 connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        web3 = connection.web3
        
        # Get user's token balance
        try:
            balance = nft_manager_contract.functions.balanceOf(user_address).call()
            
            positions = []
            for i in range(balance):
                token_id = nft_manager_contract.functions.tokenOfOwnerByIndex(user_address, i).call()
                position = nft_manager_contract.functions.positions(token_id).call()
                
                positions.append({
                    "token_id": token_id,
                    "token0": position[2],
                    "token1": position[3],
                    "fee": position[4],
                    "tick_lower": position[5],
                    "tick_upper": position[6],
                    "liquidity": position[7]
                })
            
            return {
                "user_address": user_address,
                "position_count": balance,
                "positions": positions,
                "status": "success"
            }
        except Exception as e:
            return {
                "error": f"Error getting user positions: {str(e)}",
                "status": "error"
            }
    except Exception as e:
        error_msg = f"Error getting user positions: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_perp_positions():
    """
    Get the user's perpetual positions on SparkDEX.
    
    Returns:
        A dictionary containing the user's perpetual positions
    """
    try:
        # Get account from private key
        _, user_address = _get_account_from_private_key()
        if not user_address:
            return {
                "error": "Failed to get account from private key",
                "status": "error"
            }
        
        # Get position manager contract
        position_manager_address = SPARKDEX_CONTRACTS["positionManager"]
        position_manager_contract = _get_contract(position_manager_address)
        
        if not position_manager_contract:
            return {
                "error": f"Failed to get contract instance for {position_manager_address}",
                "status": "error"
            }
        
        # Try to get user's positions
        try:
            # This is a placeholder - actual method depends on the contract implementation
            positions_count = position_manager_contract.functions.getUserPositionsCount(user_address).call()
            positions = []
            
            for i in range(positions_count):
                position_info = position_manager_contract.functions.getUserPosition(user_address, i).call()
                positions.append({
                    "index": i,
                    "market": position_info[0],
                    "size": position_info[1],
                    "collateral": position_info[2],
                    "entry_price": position_info[3],
                    "is_long": position_info[4]
                })
            
            return {
                "user_address": user_address,
                "positions_count": positions_count,
                "positions": positions,
                "status": "success"
            }
        except Exception as e:
            return {
                "error": f"Error getting perp positions: {str(e)}",
                "message": "This function may need adjustment based on the actual contract implementation",
                "status": "error"
            }
    except Exception as e:
        error_msg = f"Error getting perpetual positions: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_detailed_pool_data(pool_address: str):
    """
    Get detailed data for a SparkDEX V3 pool.
    
    Args:
        pool_address: The address of the pool contract
        
    Returns:
        A dictionary containing detailed information about the pool
    """
    try:
        # Get pool contract
        pool_contract = _get_contract(pool_address, "v3_pool_abi")
        if not pool_contract:
            return {
                "error": f"Failed to get contract instance for pool {pool_address}",
                "status": "error"
            }
        
        # Get basic pool information
        token0 = pool_contract.functions.token0().call()
        token1 = pool_contract.functions.token1().call()
        fee = pool_contract.functions.fee().call()
        
        # Get token contracts
        token0_contract = _get_contract(token0)
        token1_contract = _get_contract(token1)
        
        # Get token information
        token0_symbol = token0_contract.functions.symbol().call() if token0_contract else "Unknown"
        token1_symbol = token1_contract.functions.symbol().call() if token1_contract else "Unknown"
        token0_decimals = token0_contract.functions.decimals().call() if token0_contract else 18
        token1_decimals = token1_contract.functions.decimals().call() if token1_contract else 18
        
        # Get pool state
        slot0 = pool_contract.functions.slot0().call()
        liquidity = pool_contract.functions.liquidity().call()
        
        # Calculate current price
        sqrt_price_x96 = slot0[0]
        current_tick = slot0[1]
        
        # Price = (sqrtPriceX96 / 2^96)^2
        price_raw = (sqrt_price_x96 / (2**96))**2
        
        # Adjust for decimals
        price = price_raw * (10 ** (token0_decimals - token1_decimals))
        
        # Get fee growth
        feeGrowthGlobal0X128 = pool_contract.functions.feeGrowthGlobal0X128().call()
        feeGrowthGlobal1X128 = pool_contract.functions.feeGrowthGlobal1X128().call()
        
        return {
            "address": pool_address,
            "token0": {
                "address": token0,
                "symbol": token0_symbol,
                "decimals": token0_decimals
            },
            "token1": {
                "address": token1,
                "symbol": token1_symbol,
                "decimals": token1_decimals
            },
            "fee": fee,
            "feePercent": fee / 10000,
            "liquidity": liquidity,
            "sqrtPriceX96": sqrt_price_x96,
            "tick": current_tick,
            "price": price,
            "feeGrowthGlobal0X128": feeGrowthGlobal0X128,
            "feeGrowthGlobal1X128": feeGrowthGlobal1X128,
            "status": "success"
        }
    except Exception as e:
        error_msg = f"Error getting detailed pool data: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_token_info(token_address: str):
    """
    Get information about an ERC20 token.
    
    Args:
        token_address: The address of the token contract
        
    Returns:
        A dictionary containing information about the token
    """
    try:
        # Get token contract using our ERC20 ABI
        token_contract = _get_contract(token_address, load_abi('erc20'))
        if not token_contract:
            return {
                "error": f"Failed to get contract instance for token {token_address}",
                "status": "error"
            }
        
        # Get token information
        try:
            name = token_contract.functions.name().call()
        except Exception:
            name = "Unknown"
            
        try:
            symbol = token_contract.functions.symbol().call()
        except Exception:
            symbol = "Unknown"
            
        try:
            decimals = token_contract.functions.decimals().call()
        except Exception:
            decimals = 18
            
        try:
            total_supply_raw = token_contract.functions.totalSupply().call()
            total_supply = total_supply_raw / (10 ** decimals)
        except Exception:
            total_supply_raw = 0
            total_supply = 0
        
        return {
            "address": token_address,
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "totalSupply": total_supply,
            "totalSupplyRaw": total_supply_raw,
            "status": "success"
        }
    except Exception as e:
        error_msg = f"Error getting token info: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_token_balance(token_address: str, wallet_address: str = None):
    """
    Get the token balance for a wallet address.
    
    Args:
        token_address: The address of the token contract
        wallet_address: The wallet address to check balance for (default: uses connected wallet)
        
    Returns:
        A dictionary containing the token balance information
    """
    try:
        # Get Web3 connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        web3 = connection.web3
        
        # If no wallet address provided, use the connected account
        if not wallet_address:
            accounts = web3.eth.accounts
            if not accounts:
                return {
                    "error": "No wallet address provided and no accounts available",
                    "status": "error"
                }
            wallet_address = accounts[0]
        
        # Get token information first
        token_info = get_token_info(token_address)
        if token_info.get("status") != "success":
            return token_info
        
        # Get token contract using our ERC20 ABI
        token_contract = _get_contract(token_address, load_abi('erc20'))
        if not token_contract:
            return {
                "error": f"Failed to get contract instance for token {token_address}",
                "status": "error"
            }
        
        # Get balance
        balance_raw = token_contract.functions.balanceOf(wallet_address).call()
        decimals = token_info.get("decimals", 18)
        balance = balance_raw / (10 ** decimals)
        
        return {
            "address": token_address,
            "wallet": wallet_address,
            "name": token_info.get("name"),
            "symbol": token_info.get("symbol"),
            "decimals": decimals,
            "balance": balance,
            "balanceRaw": balance_raw,
            "status": "success"
        }
    except Exception as e:
        error_msg = f"Error getting token balance: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def add_liquidity(token0_address: str, token1_address: str, amount0: str, amount1: str, 
                 fee: int = 3000, tick_lower: int = None, tick_upper: int = None, 
                 slippage: float = 0.5, private_key: str = None):
    """
    Add liquidity to a SparkDEX V3 pool.
    
    Args:
        token0_address: The address of the first token in the pair
        token1_address: The address of the second token in the pair
        amount0: The amount of token0 to add
        amount1: The amount of token1 to add
        fee: The fee tier of the pool (default: 3000 = 0.3%)
        tick_lower: The lower tick of the position (default: None, will use a standard range)
        tick_upper: The upper tick of the position (default: None, will use a standard range)
        slippage: The maximum slippage percentage (default: 0.5%)
        private_key: The private key to use for the transaction (default: uses environment variable)
        
    Returns:
        A dictionary containing the transaction details
    """
    try:
        # Validate addresses
        if not Web3.is_address(token0_address):
            return {
                "error": f"Invalid token0 address: {token0_address}",
                "status": "error"
            }
        
        if not Web3.is_address(token1_address):
            return {
                "error": f"Invalid token1 address: {token1_address}",
                "status": "error"
            }
        
        # Get account from private key
        account, from_address = _get_account_from_private_key(private_key)
        if not account:
            return {
                "error": "Failed to get account from private key",
                "status": "error"
            }
        
        # Get Web3 connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        web3 = connection.web3
        
        # Ensure PoA middleware is added
        _ensure_poa_middleware(web3)
        
        # Get position manager contract
        nft_manager_address = SPARKDEX_CONTRACTS["nonfungiblePositionManager"]
        nft_manager_contract = _get_contract(nft_manager_address)
        
        if not nft_manager_contract:
            return {
                "error": f"Failed to get contract instance for {nft_manager_address}",
                "status": "error"
            }
        
        # Get token contracts
        token0_contract = _get_contract(token0_address)
        if not token0_contract:
            return {
                "error": f"Failed to get contract instance for {token0_address}",
                "status": "error"
            }
        
        token1_contract = _get_contract(token1_address)
        if not token1_contract:
            return {
                "error": f"Failed to get contract instance for {token1_address}",
                "status": "error"
            }
        
        # Get token decimals
        try:
            token0_decimals = token0_contract.functions.decimals().call()
            token1_decimals = token1_contract.functions.decimals().call()
            
            amount0_wei = int(float(amount0) * 10**token0_decimals)
            amount1_wei = int(float(amount1) * 10**token1_decimals)
        except Exception as e:
            return {
                "error": f"Error getting token decimals: {str(e)}",
                "status": "error"
            }
        
        # Check if pool exists
        factory_address = SPARKDEX_CONTRACTS["v3Factory"]
        factory_contract = _get_contract(factory_address, "v3_factory_abi")
        
        if not factory_contract:
            return {
                "error": f"Failed to get contract instance for {factory_address}",
                "status": "error"
            }
        
        try:
            pool_address = factory_contract.functions.getPool(token0_address, token1_address, fee).call()
            
            if pool_address == '0x0000000000000000000000000000000000000000':
                # Pool doesn't exist, we need to create it
                logger.info(f"Pool doesn't exist for {token0_address} and {token1_address} with fee {fee}, creating...")
                
                # Create pool transaction
                create_pool_tx = factory_contract.functions.createPool(
                    token0_address,
                    token1_address,
                    fee
                ).build_transaction({
                    'from': from_address,
                    'nonce': web3.eth.get_transaction_count(from_address),
                    'gas': 3000000,
                    'gasPrice': web3.eth.gas_price,
                    'chainId': web3.eth.chain_id
                })
                
                # Sign and send transaction using our helper function
                tx_hash = _sign_and_send_transaction(web3, create_pool_tx, account)
                receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
                
                # Get the pool address from the event logs or call getPool again
                pool_address = factory_contract.functions.getPool(token0_address, token1_address, fee).call()
                
                if pool_address == '0x0000000000000000000000000000000000000000':
                    return {
                        "error": "Failed to create pool",
                        "status": "error"
                    }
                
                logger.info(f"Pool created at {pool_address}")
                
                # Initialize the pool with a price
                pool_contract = _get_contract(pool_address, "v3_pool_abi")
                
                # Calculate initial sqrt price (assuming 1:1 for simplicity)
                # In a real implementation, you would want to use a more accurate initial price
                initial_price = 1.0  # 1 token0 = 1 token1
                sqrt_price_x96 = int((initial_price ** 0.5) * (2 ** 96))
                
                # Initialize pool
                init_tx = pool_contract.functions.initialize(sqrt_price_x96).build_transaction({
                    'from': from_address,
                    'nonce': web3.eth.get_transaction_count(from_address),
                    'gas': 200000,
                    'gasPrice': web3.eth.gas_price,
                    'chainId': web3.eth.chain_id
                })
                
                # Sign and send transaction using our helper function
                tx_hash = _sign_and_send_transaction(web3, init_tx, account)
                receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
                
                logger.info(f"Pool initialized with sqrt price {sqrt_price_x96}")
            
            # Get pool information to determine ticks if not provided
            pool_contract = _get_contract(pool_address)
            if not pool_contract:
                return {
                    "error": f"Failed to get contract instance for pool {pool_address}",
                    "status": "error"
                }
            
            # Get current tick from pool
            slot0 = pool_contract.functions.slot0().call()
            current_tick = slot0[1]
            
            # If tick range not provided, use a standard range around the current tick
            if tick_lower is None or tick_upper is None:
                # Get tick spacing for this fee tier
                tick_spacing = factory_contract.functions.feeAmountTickSpacing(fee).call()
                
                # Set a range of ±10% around the current price (simplified)
                # In a real implementation, you would want to use a more sophisticated approach
                if tick_lower is None:
                    tick_lower = current_tick - (10 * tick_spacing)
                    # Ensure tick_lower is a multiple of tick_spacing
                    tick_lower = tick_lower - (tick_lower % tick_spacing)
                
                if tick_upper is None:
                    tick_upper = current_tick + (10 * tick_spacing)
                    # Ensure tick_upper is a multiple of tick_spacing
                    tick_upper = tick_upper - (tick_upper % tick_spacing)
            
            # Check allowances and approve if needed
            for token_address, token_contract, amount_wei in [
                (token0_address, token0_contract, amount0_wei),
                (token1_address, token1_contract, amount1_wei)
            ]:
                try:
                    allowance = token_contract.functions.allowance(from_address, nft_manager_address).call()
                    if allowance < amount_wei:
                        # Approve position manager to spend tokens
                        approve_tx = token_contract.functions.approve(
                            nft_manager_address,
                            2**256 - 1  # Max uint256 value
                        ).build_transaction({
                            'from': from_address,
                            'nonce': web3.eth.get_transaction_count(from_address),
                            'gas': 100000,
                            'gasPrice': web3.eth.gas_price,
                            'chainId': web3.eth.chain_id
                        })
                        
                        # Sign and send approval transaction using our helper function
                        tx_hash = _sign_and_send_transaction(web3, approve_tx, account)
                        web3.eth.wait_for_transaction_receipt(tx_hash)
                        
                        logger.info(f"Approved position manager to spend {token_address}: {web3.to_hex(tx_hash)}")
                except Exception as e:
                    return {
                        "error": f"Error approving tokens: {str(e)}",
                        "status": "error"
                    }
            
            # Calculate amount minimums based on slippage
            amount0_min = int(amount0_wei * (1 - slippage / 100))
            amount1_min = int(amount1_wei * (1 - slippage / 100))
            
            # Current timestamp plus 20 minutes
            deadline = web3.eth.get_block('latest').timestamp + 1200
            
            # Build mint transaction
            mint_params = {
                'token0': token0_address,
                'token1': token1_address,
                'fee': fee,
                'tickLower': tick_lower,
                'tickUpper': tick_upper,
                'amount0Desired': amount0_wei,
                'amount1Desired': amount1_wei,
                'amount0Min': amount0_min,
                'amount1Min': amount1_min,
                'recipient': from_address,
                'deadline': deadline
            }
            
            mint_tx = nft_manager_contract.functions.mint(mint_params).build_transaction({
                'from': from_address,
                'nonce': web3.eth.get_transaction_count(from_address),
                'gas': 500000,
                'gasPrice': web3.eth.gas_price,
                'chainId': web3.eth.chain_id
            })
            
            # Sign and send mint transaction using our helper function
            tx_hash = _sign_and_send_transaction(web3, mint_tx, account)
            logger.info(f"Mint transaction sent: {web3.to_hex(tx_hash)}")
            
            # Wait for receipt to get token ID
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Try to extract token ID from event logs
            token_id = None
            for log in receipt.logs:
                if log['address'].lower() == nft_manager_address.lower():
                    # This is a simplified approach - in a real implementation, 
                    # you would want to decode the event data properly
                    try:
                        # Get the IncreaseLiquidity event
                        event_signature = web3.keccak(text="IncreaseLiquidity(uint256,uint128,uint256,uint256)").hex()
                        if log['topics'][0].hex() == event_signature:
                            token_id = int(log['topics'][1].hex(), 16)
                            break
                    except Exception:
                        pass
            
            return {
                "transaction_hash": web3.to_hex(tx_hash),
                "from_address": from_address,
                "pool_address": pool_address,
                "token0": token0_address,
                "token1": token1_address,
                "amount0": amount0,
                "amount1": amount1,
                "amount0_wei": amount0_wei,
                "amount1_wei": amount1_wei,
                "tick_lower": tick_lower,
                "tick_upper": tick_upper,
                "token_id": token_id,
                "status": "success"
            }
        except Exception as e:
            return {
                "error": f"Error adding liquidity: {str(e)}",
                "status": "error"
            }
    except Exception as e:
        error_msg = f"Error adding liquidity: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def create_pool(token0_address: str, token1_address: str, fee: int = 3000, initial_price: float = 1.0, private_key: str = None):
    """
    Create a new SparkDEX V3 pool.
    
    Args:
        token0_address: The address of the first token in the pair
        token1_address: The address of the second token in the pair
        fee: The fee tier of the pool (default: 3000 = 0.3%)
        initial_price: The initial price of token1 in terms of token0 (default: 1.0)
        private_key: The private key to use for the transaction (default: uses environment variable)
        
    Returns:
        A dictionary containing the transaction details
    """
    try:
        # Validate addresses
        if not Web3.is_address(token0_address):
            return {
                "error": f"Invalid token0 address: {token0_address}",
                "status": "error"
            }
        
        if not Web3.is_address(token1_address):
            return {
                "error": f"Invalid token1 address: {token1_address}",
                "status": "error"
            }
        
        # Get account from private key
        account, from_address = _get_account_from_private_key(private_key)
        if not account:
            return {
                "error": "Failed to get account from private key",
                "status": "error"
            }
        
        # Get Web3 connection
        connection = get_evm_connection()
        if not connection or not connection.connected:
            return {
                "error": "Failed to connect to Ethereum node",
                "status": "error"
            }
        
        web3 = connection.web3
        
        # Ensure PoA middleware is added
        _ensure_poa_middleware(web3)
        
        # Get factory contract
        factory_address = SPARKDEX_CONTRACTS["v3Factory"]
        factory_contract = _get_contract(factory_address, "v3_factory_abi")
        
        if not factory_contract:
            return {
                "error": f"Failed to get contract instance for {factory_address}",
                "status": "error"
            }
        
        # Check if pool already exists
        try:
            existing_pool = factory_contract.functions.getPool(token0_address, token1_address, fee).call()
            
            if existing_pool != '0x0000000000000000000000000000000000000000':
                return {
                    "error": f"Pool already exists at {existing_pool}",
                    "pool_address": existing_pool,
                    "status": "error"
                }
            
            # Create pool transaction
            create_pool_tx = factory_contract.functions.createPool(
                token0_address,
                token1_address,
                fee
            ).build_transaction({
                'from': from_address,
                'nonce': web3.eth.get_transaction_count(from_address),
                'gas': 3000000,
                'gasPrice': web3.eth.gas_price,
                'chainId': web3.eth.chain_id
            })
            
            # Sign and send transaction using our helper function
            tx_hash = _sign_and_send_transaction(web3, create_pool_tx, account)
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Get the pool address
            pool_address = factory_contract.functions.getPool(token0_address, token1_address, fee).call()
            
            if pool_address == '0x0000000000000000000000000000000000000000':
                return {
                    "error": "Failed to create pool",
                    "status": "error"
                }
            
            logger.info(f"Pool created at {pool_address}")
            
            # Initialize the pool with a price
            pool_contract = _get_contract(pool_address, "v3_pool_abi")
            
            # Calculate sqrt price
            # sqrtPriceX96 = sqrt(price) * 2^96
            sqrt_price_x96 = int((initial_price ** 0.5) * (2 ** 96))
            
            # Initialize pool
            init_tx = pool_contract.functions.initialize(sqrt_price_x96).build_transaction({
                'from': from_address,
                'nonce': web3.eth.get_transaction_count(from_address),
                'gas': 200000,
                'gasPrice': web3.eth.gas_price,
                'chainId': web3.eth.chain_id
            })
            
            # Sign and send transaction using our helper function
            tx_hash = _sign_and_send_transaction(web3, init_tx, account)
            receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"Pool initialized with sqrt price {sqrt_price_x96}")
            
            # Get token information
            token0_contract = _get_contract(token0_address)
            token1_contract = _get_contract(token1_address)
            
            token0_symbol = token0_contract.functions.symbol().call() if token0_contract else "Unknown"
            token1_symbol = token1_contract.functions.symbol().call() if token1_contract else "Unknown"
            
            return {
                "transaction_hash": web3.to_hex(tx_hash),
                "from_address": from_address,
                "pool_address": pool_address,
                "token0": {
                    "address": token0_address,
                    "symbol": token0_symbol
                },
                "token1": {
                    "address": token1_address,
                    "symbol": token1_symbol
                },
                "fee": fee,
                "fee_percent": fee / 10000,
                "initial_price": initial_price,
                "sqrt_price_x96": sqrt_price_x96,
                "status": "success"
            }
        except Exception as e:
            return {
                "error": f"Error creating pool: {str(e)}",
                "status": "error"
            }
    except Exception as e:
        error_msg = f"Error creating pool: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "status": "error"
        }

def get_pool_details_by_address(pool_address: str) -> dict:
    """
    Get detailed information about a SparkDEX V3 pool using its direct address.
    
    Args:
        pool_address (str): The address of the SparkDEX V3 pool
        
    Returns:
        dict: A dictionary containing detailed pool information
    """
    try:
        # Validate the pool address
        if not Web3.is_address(pool_address):
            return {"error": f"Invalid pool address format: {pool_address}"}
        
        # Get the pool contract
        pool_contract = _get_contract(pool_address, "v3_pool_abi")
        
        if not pool_contract:
            return {"error": f"Could not get contract instance for pool: {pool_address}"}
        
        # Get basic pool information
        token0_address = pool_contract.functions.token0().call()
        token1_address = pool_contract.functions.token1().call()
        fee = pool_contract.functions.fee().call()
        liquidity = pool_contract.functions.liquidity().call()
        tick_spacing = pool_contract.functions.tickSpacing().call()
        factory_address = pool_contract.functions.factory().call()
        
        # Get slot0 data which contains current price and tick
        slot0_data = pool_contract.functions.slot0().call()
        sqrt_price_x96 = slot0_data[0]
        current_tick = slot0_data[1]
        
        # Get token information
        token0_contract = _get_contract(token0_address, "erc20")
        token1_contract = _get_contract(token1_address, "erc20")
        
        # Try to get token symbols from our dictionary first
        token0_symbol = get_token_by_address(token0_address) or "Unknown"
        token1_symbol = get_token_by_address(token1_address) or "Unknown"
        
        # Get token decimals from our dictionary or from the contract
        token0_decimals = 18
        token1_decimals = 18
        
        # Try to get decimals from our dictionary first
        if token0_symbol != "Unknown" and token0_symbol in TOKEN_INFO:
            token0_decimals = TOKEN_INFO[token0_symbol]["decimals"]
        elif token0_contract:
            try:
                token0_decimals = token0_contract.functions.decimals().call()
            except Exception as e:
                logging.error(f"Error getting token0 decimals: {e}")
        
        if token1_symbol != "Unknown" and token1_symbol in TOKEN_INFO:
            token1_decimals = TOKEN_INFO[token1_symbol]["decimals"]
        elif token1_contract:
            try:
                token1_decimals = token1_contract.functions.decimals().call()
            except Exception as e:
                logging.error(f"Error getting token1 decimals: {e}")
        
        # If we still don't have symbols, try to get them from the contract
        if token0_symbol == "Unknown" and token0_contract:
            try:
                token0_symbol = token0_contract.functions.symbol().call()
            except Exception as e:
                logging.error(f"Error getting token0 symbol: {e}")
        
        if token1_symbol == "Unknown" and token1_contract:
            try:
                token1_symbol = token1_contract.functions.symbol().call()
            except Exception as e:
                logging.error(f"Error getting token1 symbol: {e}")
        
        # Calculate the price in token terms
        price = calculate_price_from_sqrt_price_x96(sqrt_price_x96, token0_decimals, token1_decimals)
        
        # Estimate USD values
        # Current prices in USD (these should be updated with real market data)
        token_prices_usd = {
            "WFLR": 0.0142,  # Current price of WFLR in USD
            "USDT": 1.0,     # Stablecoin
            "USDC": 1.0      # Stablecoin
        }
        
        # Calculate USD values
        usd_price = None
        usd_liquidity_estimate = None
        
        # If we have USD prices for both tokens
        if token0_symbol in token_prices_usd and token1_symbol in token_prices_usd:
            token0_usd = token_prices_usd[token0_symbol]
            token1_usd = token_prices_usd[token1_symbol]
            
            # Price in USD
            usd_price = price * token1_usd / token0_usd
        
        # Format the result
        result = {
            "pool_address": pool_address,
            "token0": {
                "address": token0_address,
                "symbol": token0_symbol,
                "decimals": token0_decimals
            },
            "token1": {
                "address": token1_address,
                "symbol": token1_symbol,
                "decimals": token1_decimals
            },
            "fee": fee,
            "fee_percent": fee / 10000,
            "liquidity": liquidity,
            "tick_spacing": tick_spacing,
            "current_tick": current_tick,
            "sqrt_price_x96": sqrt_price_x96,
            "price": price,
            "price_description": f"1 {token0_symbol} = {price} {token1_symbol}",
            "factory_address": factory_address
        }
        
        # Add USD values if available
        if usd_price is not None:
            result["usd_price"] = usd_price
            result["usd_price_description"] = f"1 {token0_symbol} ≈ ${usd_price:.6f} USD"
        
        return result
    
    except Exception as e:
        logging.error(f"Error in get_pool_details_by_address: {e}")
        return {"error": f"Failed to get pool details: {str(e)}"}

def calculate_price_from_sqrt_price_x96(sqrt_price_x96: int, token0_decimals: int, token1_decimals: int) -> float:
    """
    Calculate the price from sqrtPriceX96 value.
    
    Args:
        sqrt_price_x96 (int): The sqrtPriceX96 value from the pool
        token0_decimals (int): Decimals for token0
        token1_decimals (int): Decimals for token1
        
    Returns:
        float: The price of token0 in terms of token1
    """
    try:
        # Convert to decimal for precision
        sqrt_price = Decimal(sqrt_price_x96) / Decimal(2**96)
        price = sqrt_price * sqrt_price
        
        # Adjust for token decimals
        decimal_adjustment = Decimal(10**(token1_decimals - token0_decimals))
        adjusted_price = price * decimal_adjustment
        
        return float(adjusted_price)
    except Exception as e:
        logging.error(f"Error calculating price: {e}")
        return 0

def _sign_and_send_transaction(web3, tx, account):
    """Sign and send a transaction."""
    try:
        logger.info("Starting inline transaction signing process")
        try:
            # Log transaction details
            logger.info(f"Transaction to sign: gas={tx.get('gas')}, nonce={tx.get('nonce')}")
            logger.info(f"Transaction destination: {tx.get('to')}")
            
            # Ensure POA middleware is added
            logger.debug("Ensuring POA middleware is added")
            if ExtraDataToPOAMiddleware not in web3.middleware_onion:
                web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
                logger.debug("Added POA middleware")
            
            # Log account details (safely)
            logger.info(f"Signing with account: {account.address}")
            
            # Sign the transaction
            logger.info("Signing transaction...")
            signed_tx = web3.eth.account.sign_transaction(tx, private_key=account.key)
            logger.info("Transaction signed successfully")
            
            # Send the transaction
            logger.info("Sending raw transaction to network...")
            if hasattr(signed_tx, 'raw_transaction'):
                logger.debug("Using raw_transaction attribute (newer Web3.py)")
                tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            elif hasattr(signed_tx, 'rawTransaction'):
                logger.debug("Using rawTransaction attribute (older Web3.py)")
                tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            else:
                error_msg = "Cannot find raw transaction data in signed transaction"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.info(f"Raw transaction sent successfully with hash: {tx_hash.hex()}")
            
            # Don't convert to hex string here - keep the original tx_hash object
            # This should avoid the type conversion issue
            
        except Exception as e:
            error_msg = f"Error in inline transaction signing/sending: {str(e)}"
            logger.error(error_msg)
            
            # Log more details about the transaction that failed
            try:
                logger.error("Transaction that failed:")
                for key, value in tx.items():
                    logger.error(f"  {key}: {value}")
            except:
                logger.error("Could not log transaction details")
            
            raise Exception(error_msg)
        
        # Now continue with the original code, using tx_hash directly
        logger.info(f"Transaction hash (for logging): {tx_hash.hex()}")
        logger.info(f"Transaction hash type: {type(tx_hash)}")

        # Wait for receipt using the original tx_hash object
        logger.info("Waiting for transaction receipt...")
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        
        return tx_hash
        
    except Exception as e:
        error_msg = f"Error in inline transaction signing/sending: {str(e)}"
        logger.error(error_msg)
        
        # Log more details about the transaction that failed
        try:
            logger.error("Transaction that failed:")
            for key, value in tx.items():
                logger.error(f"  {key}: {value}")
        except:
            logger.error("Could not log transaction details")
            
        raise Exception(error_msg)

def _ensure_poa_middleware(web3: object) -> bool:
    """Ensure that the POA middleware is injected into the web3 instance."""
    try:
        # Check if middleware is already in the stack
        if ExtraDataToPOAMiddleware not in web3.middleware_onion:
            # Use inject without specifying layer if it's not already present
            web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        return True
    except Exception as e:
        # Alternative approach if the above fails
        try:
            # Try adding it without specifying the layer
            web3.middleware_onion.add(ExtraDataToPOAMiddleware)
            return True
        except:
            # If all else fails, try a different approach
            try:
                web3.middleware_onion.inject(ExtraDataToPOAMiddleware)
                return True
            except:
                return False