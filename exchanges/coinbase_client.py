"""Coinbase Exchange Client"""
import ccxt.async_support as ccxt
import logging

logger = logging.getLogger(__name__)

class CoinbaseClient:
    def __init__(self, api_key=None, api_secret=None, testnet=False):
        self.exchange = ccxt.coinbase({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)
        logger.info("Coinbase client initialized")
    
    async def fetch_ticker(self, symbol):
        return await self.exchange.fetch_ticker(symbol)
    
    async def fetch_order_book(self, symbol, limit=20):
        return await self.exchange.fetch_order_book(symbol, limit)
    
    async def create_order(self, symbol, order_type, side, amount, price=None):
        return await self.exchange.create_order(symbol, order_type, side, amount, price)
    
    async def fetch_balance(self):
        return await self.exchange.fetch_balance()
    
    async def close(self):
        await self.exchange.close()
