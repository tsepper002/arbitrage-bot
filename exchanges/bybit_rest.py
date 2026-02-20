import time
import hmac
import hashlib
import aiohttp
import logging

from .base import BaseExchange

logger = logging.getLogger("bybit_rest")


class BybitREST(BaseExchange):
    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.bybit.com"
        self.recv_window = "5000"

    def _generate_signature(self, timestamp: str, query_string: str) -> str:
        """Generate HMAC-SHA256 signature for Bybit v5 API."""
        param_str = timestamp + self.api_key + self.recv_window + query_string
        return hmac.new(
            self.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _auth_headers(self, query_string: str = "") -> dict:
        """Generate authenticated headers for Bybit v5 API."""
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret are required for authenticated endpoints")
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp, query_string)
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": self.recv_window,
        }

    async def get_price(self, symbol: str) -> float:
        """Fetch latest price for a symbol using Bybit v5 public API."""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/v5/market/tickers?category=spot&symbol={symbol}"
            async with session.get(url) as response:
                data = await response.json()
                if data.get("retCode") != 0:
                    raise RuntimeError(f"Bybit get price failed: {data}")
                return float(data["result"]["list"][0]["lastPrice"])

    async def get_balance(self, account_type: str = "UNIFIED") -> dict:
        """
        Fetch account balance using Bybit v5 authenticated API.
        Requires valid api_key and api_secret.
        """
        query_string = f"accountType={account_type}"
        headers = self._auth_headers(query_string)
        url = f"{self.base_url}/v5/account/wallet-balance?{query_string}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                data = await response.json()
                if data.get("retCode") != 0:
                    raise RuntimeError(f"Bybit get balance failed: {data}")
                return data["result"]

    async def place_order(self, symbol: str, amount: float, price: float) -> dict:
        """Placeholder for order placement."""
        pass

    async def connect(self):
        """REST client does not need a persistent connection."""
        pass
