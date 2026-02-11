"""
Binance REST Client - REAL IMPLEMENTATION
Uses ccxt library for robust API interaction
"""
import ccxt.async_support as ccxt
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class BinanceRESTClient:
    """Real Binance REST API client with full functionality."""
    
    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = False):
        """
        Initialize Binance REST client.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet environment
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Initialize ccxt Binance exchange
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',  # spot, future, swap
                'adjustForTimeDifference': True,  # Handle time sync issues
            }
        })
        
        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("Binance REST client initialized (TESTNET)")
        else:
            logger.info("Binance REST client initialized (LIVE)")
    
    async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Fetch ticker data for a symbol.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
        
        Returns:
            Ticker data or None on error
        """
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            return None
    
    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """
        Fetch order book (depth) for a symbol.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            limit: Number of levels to fetch (default 20)
        
        Returns:
            Order book data or None on error
        """
        try:
            orderbook = await self.exchange.fetch_order_book(symbol, limit)
            return orderbook
        except Exception as e:
            logger.error(f"Error fetching orderbook for {symbol}: {e}")
            return None
    
    async def create_market_order(self, symbol: str, side: str, amount: float) -> Optional[Dict]:
        """
        Create a market order.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Order amount in base currency
        
        Returns:
            Order info or None on error
        """
        try:
            order = await self.exchange.create_market_order(symbol, side, amount)
            logger.info(f"✅ Binance market {side} order created: {symbol} {amount}")
            return order
        except Exception as e:
            logger.error(f"❌ Error creating market order: {e}")
            return None
    
    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float
    ) -> Optional[Dict]:
        """
        Create a limit order.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'buy' or 'sell'
            amount: Order amount in base currency
            price: Limit price
        
        Returns:
            Order info or None on error
        """
        try:
            order = await self.exchange.create_limit_order(symbol, side, amount, price)
            logger.info(f"✅ Binance limit {side} order created: {symbol} {amount} @ {price}")
            return order
        except Exception as e:
            logger.error(f"❌ Error creating limit order: {e}")
            return None
    
    async def fetch_balance(self) -> Optional[Dict]:
        """
        Fetch account balance.
        
        Returns:
            Balance data or None on error
        """
        try:
            balance = await self.exchange.fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return None
    
    async def fetch_my_trades(self, symbol: str, limit: int = 50) -> Optional[List[Dict]]:
        """
        Fetch recent trades for an account.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            limit: Number of trades to fetch
        
        Returns:
            List of trades or None on error
        """
        try:
            trades = await self.exchange.fetch_my_trades(symbol, limit=limit)
            return trades
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return None
    
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Fetch open orders.
        
        Args:
            symbol: Trading pair (optional, fetch all if None)
        
        Returns:
            List of open orders or None on error
        """
        try:
            orders = await self.exchange.fetch_open_orders(symbol)
            return orders
        except Exception as e:
            logger.error(f"Error fetching open orders: {e}")
            return None
    
    async def cancel_order(self, order_id: str, symbol: str) -> Optional[Dict]:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair
        
        Returns:
            Cancellation result or None on error
        """
        try:
            result = await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"✅ Binance order cancelled: {order_id}")
            return result
        except Exception as e:
            logger.error(f"❌ Error cancelling order: {e}")
            return None
    
    async def fetch_trading_fees(self, symbol: Optional[str] = None) -> Optional[Dict]:
        """
        Fetch trading fees.
        
        Args:
            symbol: Trading pair (optional)
        
        Returns:
            Fee data or None on error
        """
        try:
            fees = await self.exchange.fetch_trading_fees()
            if symbol:
                return fees.get(symbol, None)
            return fees
        except Exception as e:
            logger.error(f"Error fetching fees: {e}")
            return None
    
    async def close(self):
        """Close the exchange connection."""
        try:
            await self.exchange.close()
            logger.info("Binance REST client closed")
        except Exception as e:
            logger.error(f"Error closing Binance client: {e}")


async def _test_binance_rest():
    """Test function for Binance REST client."""
    import os
    
    # Get API keys from environment (if available)
    api_key = os.getenv('BINANCE_API_KEY', '')
    api_secret = os.getenv('BINANCE_API_SECRET', '')
    
    # Use testnet if no keys
    testnet = not (api_key and api_secret)
    
    client = BinanceRESTClient(api_key, api_secret, testnet=testnet)
    
    try:
        # Test ticker
        print("\n--- Testing Ticker ---")
        ticker = await client.fetch_ticker('BTC/USDT')
        if ticker:
            print(f"BTC/USDT Price: ${ticker['last']:.2f}")
        
        # Test orderbook
        print("\n--- Testing Orderbook ---")
        orderbook = await client.fetch_order_book('BTC/USDT', limit=5)
        if orderbook:
            print(f"Best Bid: ${orderbook['bids'][0][0]:.2f}")
            print(f"Best Ask: ${orderbook['asks'][0][0]:.2f}")
        
        # Test balance (if keys provided)
        if api_key and api_secret:
            print("\n--- Testing Balance ---")
            balance = await client.fetch_balance()
            if balance:
                print(f"Total assets: {len(balance['total'])} currencies")
        
    finally:
        await client.close()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_test_binance_rest())
