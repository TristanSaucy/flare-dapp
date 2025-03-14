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
        abi: The contract ABI (optional)
        
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
        
        # Get ABI if not provided
        if not abi:
            abi = _get_contract_abi(contract_address)
            if not abi:
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
        factory_contract = _get_contract(factory_address)
        
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
        factory_contract = _get_contract(factory_address)
        
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
            pool_contract = _get_contract(pool_address)
            
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
        quoter_contract = _get_contract(quoter_address)
        
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
        # Validate addresses
        if not Web3.is_address(token_in_address):
            return {
                "error": f"Invalid input token address: {token_in_address}",
                "status": "error"
            }
        
        if not Web3.is_address(token_out_address):
            return {
                "error": f"Invalid output token address: {token_out_address}",
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
        
        # Get router contract
        router_address = SPARKDEX_CONTRACTS["swapRouter"]
        router_contract = _get_contract(router_address)
        
        if not router_contract:
            return {
                "error": f"Failed to get contract instance for {router_address}",
                "status": "error"
            }
        
        # Get token contracts
        token_in_contract = _get_contract(token_in_address)
        if not token_in_contract:
            return {
                "error": f"Failed to get contract instance for {token_in_address}",
                "status": "error"
            }
        
        # Get token decimals
        try:
            decimals = token_in_contract.functions.decimals().call()
            amount_in_wei = int(float(amount_in) * 10**decimals)
        except Exception:
            # Default to 18 decimals if we can't get the actual value
            amount_in_wei = int(float(amount_in) * 10**18)
        
        # Check allowance and approve if needed
        try:
            allowance = token_in_contract.functions.allowance(from_address, router_address).call()
            if allowance < amount_in_wei:
                # Approve router to spend tokens
                approve_tx = token_in_contract.functions.approve(
                    router_address,
                    2**256 - 1  # Max uint256 value
                ).build_transaction({
                    'from': from_address,
                    'nonce': web3.eth.get_transaction_count(from_address),
                    'gas': 100000,
                    'gasPrice': web3.eth.gas_price
                })
                
                # Sign and send approval transaction
                signed_tx = web3.eth.account.sign_transaction(approve_tx, account.key)
                tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
                web3.eth.wait_for_transaction_receipt(tx_hash)
                
                logger.info(f"Approved router to spend tokens: {web3.to_hex(tx_hash)}")
        except Exception as e:
            return {
                "error": f"Error approving tokens: {str(e)}",
                "status": "error"
            }
        
        # Get quote for minimum amount out
        quoter_address = SPARKDEX_CONTRACTS["quoterV2"]
        quoter_contract = _get_contract(quoter_address)
        
        if not quoter_contract:
            return {
                "error": f"Failed to get contract instance for {quoter_address}",
                "status": "error"
            }
        
        # Default fee tier
        fee = 3000  # 0.3%
        
        # Try to get quote
        try:
            quote_params = {
                'tokenIn': token_in_address,
                'tokenOut': token_out_address,
                'fee': fee,
                'amountIn': amount_in_wei,
                'sqrtPriceLimitX96': 0
            }
            
            quote_result = quoter_contract.functions.quoteExactInputSingle(quote_params).call()
            amount_out = quote_result[0]
            
            # Apply slippage
            min_amount_out = int(amount_out * (1 - slippage / 100))
        except Exception as e:
            return {
                "error": f"Error getting quote: {str(e)}",
                "status": "error"
            }
        
        # Current timestamp plus 20 minutes
        deadline = web3.eth.get_block('latest').timestamp + 1200
        
        # Build swap transaction
        try:
            swap_params = {
                'tokenIn': token_in_address,
                'tokenOut': token_out_address,
                'fee': fee,
                'recipient': from_address,
                'amountIn': amount_in_wei,
                'amountOutMinimum': min_amount_out,
                'sqrtPriceLimitX96': 0
            }
            
            swap_tx = router_contract.functions.exactInputSingle(swap_params).build_transaction({
                'from': from_address,
                'nonce': web3.eth.get_transaction_count(from_address),
                'gas': 300000,
                'gasPrice': web3.eth.gas_price
            })
            
            # Sign and send swap transaction
            signed_tx = web3.eth.account.sign_transaction(swap_tx, account.key)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Swap transaction sent: {web3.to_hex(tx_hash)}")
            
            return {
                "transaction_hash": web3.to_hex(tx_hash),
                "from_address": from_address,
                "token_in": token_in_address,
                "token_out": token_out_address,
                "amount_in": amount_in,
                "amount_in_wei": amount_in_wei,
                "expected_amount_out": amount_out,
                "min_amount_out": min_amount_out,
                "status": "success"
            }
        except Exception as e:
            return {
                "error": f"Error executing swap: {str(e)}",
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
        pool_contract = _get_contract(pool_address)
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
        sqrtPriceX96 = slot0[0]
        current_tick = slot0[1]
        
        # Price = (sqrtPriceX96 / 2^96)^2
        price_raw = (sqrtPriceX96 / (2**96))**2
        
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
            "sqrtPriceX96": sqrtPriceX96,
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