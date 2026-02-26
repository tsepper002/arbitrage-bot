"""
Binance REST API client for authenticated operations.
Implements order placement, cancellation, balance queries, and withdrawals.
Uses native aiohttp (no ccxt dependency) for consistency with other clients.
"""
import time
import hmac
import hashlib
import socket
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base_client import BaseRESTClient

logger = logging.getLogger("binance_rest")


class BinanceRESTClient(BaseRESTClient):
    """Binance exchange REST API client."""

    BASE_URL = "https://api.binance.com"

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret, "Binance")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                family=socket.AF_INET,
                resolver=aiohttp.ThreadedResolver()
            )
            timeout = aiohttp.ClientTimeout(total=30, sock_connect=10)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for Binance API."""
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests."""
        return {
            "X-MBX-APIKEY": self.api_key
        }

    def normalize_symbol(self, symbol: str) -> str:
        """Convert BTC-USDT to BTCUSDT."""
        return symbol.replace("-", "")

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """Place an order on Binance."""
        url = f"{self.BASE_URL}/api/v3/order"

        params = {
            "symbol": self.normalize_symbol(symbol),
            "side": side.upper(),
            "type": "MARKET" if order_type == "market" else "LIMIT",
            "quantity": f"{quantity:.8f}",
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000
        }

        if order_type == "limit" and price:
            params["price"] = f"{price:.8f}"
            params["timeInForce"] = time_in_force

        params["signature"] = self._generate_signature(params)
        headers = self._get_headers()
        session = await self._get_session()

        async with session.post(url, params=params, headers=headers) as resp:
            data = await resp.json()

            if "code" in data and data.get("code", 0) < 0:
                raise Exception(f"Binance order failed: {data}")

            return {
                "order_id": str(data.get("orderId", "")),
                "status": data.get("status", "UNKNOWN"),
                "filled_qty": float(data.get("executedQty", 0)),
                "avg_price": float(data.get("price", 0)),
                "symbol": symbol,
                "side": side,
                "raw": data
            }

    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancel an order on Binance."""
        url = f"{self.BASE_URL}/api/v3/order"

        params = {
            "symbol": self.normalize_symbol(symbol),
            "orderId": order_id,
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000
        }
        params["signature"] = self._generate_signature(params)
        headers = self._get_headers()
        session = await self._get_session()

        async with session.delete(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if "code" in data and data.get("code", 0) < 0:
                raise Exception(f"Binance cancel failed: {data}")
            return {"order_id": order_id, "status": "cancelled", "raw": data}

    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Get order status on Binance."""
        url = f"{self.BASE_URL}/api/v3/order"

        params = {
            "symbol": self.normalize_symbol(symbol),
            "orderId": order_id,
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000
        }
        params["signature"] = self._generate_signature(params)
        headers = self._get_headers()
        session = await self._get_session()

        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()
            return {
                "order_id": str(data.get("orderId", "")),
                "status": data.get("status", "UNKNOWN"),
                "filled_qty": float(data.get("executedQty", 0)),
                "avg_price": float(data.get("price", 0)),
                "raw": data
            }

    async def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """Get account balances from Binance."""
        url = f"{self.BASE_URL}/api/v3/account"

        params = {
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000
        }
        params["signature"] = self._generate_signature(params)
        headers = self._get_headers()
        session = await self._get_session()

        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()

            if "code" in data and data.get("code", 0) < 0:
                raise Exception(f"Binance balance failed: {data}")

            balances = {}
            for asset in data.get("balances", []):
                free = float(asset.get("free", 0))
                if free > 0 or (currency and asset["asset"] == currency):
                    balances[asset["asset"]] = free

            if currency:
                return {currency: balances.get(currency, 0.0)}
            return balances

    async def get_trading_pairs(self) -> List[Dict[str, Any]]:
        """Get all available trading pairs from Binance."""
        url = f"{self.BASE_URL}/api/v3/exchangeInfo"
        session = await self._get_session()

        async with session.get(url) as resp:
            data = await resp.json()

            pairs = []
            for sym_info in data.get("symbols", []):
                if sym_info.get("status") == "TRADING":
                    pairs.append({
                        "symbol": f"{sym_info['baseAsset']}-{sym_info['quoteAsset']}",
                        "base": sym_info["baseAsset"],
                        "quote": sym_info["quoteAsset"],
                        "min_qty": float(next(
                            (f["minQty"] for f in sym_info.get("filters", [])
                             if f["filterType"] == "LOT_SIZE"),
                            "0.00001"
                        )),
                    })
            return pairs

    async def withdraw(
        self,
        currency: str,
        amount: float,
        address: str,
        network: Optional[str] = None,
        memo: Optional[str] = None
    ) -> Dict[str, Any]:
        """Withdraw funds from Binance."""
        url = f"{self.BASE_URL}/sapi/v1/capital/withdraw/apply"

        params = {
            "coin": currency,
            "amount": str(amount),
            "address": address,
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000
        }
        if network:
            params["network"] = network
        if memo:
            params["addressTag"] = memo

        params["signature"] = self._generate_signature(params)
        headers = self._get_headers()
        session = await self._get_session()

        async with session.post(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if "code" in data and data.get("code", 0) < 0:
                raise Exception(f"Binance withdraw failed: {data}")
            return {"withdrawal_id": data.get("id", ""), "status": "submitted", "raw": data}

    async def get_deposit_address(self, currency: str, network: Optional[str] = None) -> Dict[str, str]:
        """Get deposit address from Binance."""
        url = f"{self.BASE_URL}/sapi/v1/capital/deposit/address"

        params = {
            "coin": currency,
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000
        }
        if network:
            params["network"] = network

        params["signature"] = self._generate_signature(params)
        headers = self._get_headers()
        session = await self._get_session()

        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if "code" in data and data.get("code", 0) < 0:
                raise Exception(f"Binance deposit address failed: {data}")
            result = {"address": data.get("address", "")}
            if data.get("tag"):
                result["memo"] = data["tag"]
            return result

    async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        """Fetch ticker data for a symbol."""
        url = f"{self.BASE_URL}/api/v3/ticker/24hr"
        params = {"symbol": self.normalize_symbol(symbol)}
        session = await self._get_session()

        try:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                return {
                    "last": float(data.get("lastPrice", 0)),
                    "bid": float(data.get("bidPrice", 0)),
                    "ask": float(data.get("askPrice", 0)),
                    "volume": float(data.get("volume", 0)),
                }
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            return None

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Optional[Dict]:
        """Fetch order book for a symbol."""
        url = f"{self.BASE_URL}/api/v3/depth"
        params = {"symbol": self.normalize_symbol(symbol), "limit": limit}
        session = await self._get_session()

        try:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                return {
                    "bids": [[float(p), float(q)] for p, q in data.get("bids", [])],
                    "asks": [[float(p), float(q)] for p, q in data.get("asks", [])],
                }
        except Exception as e:
            logger.error(f"Error fetching orderbook for {symbol}: {e}")
            return None

    async def test_connectivity(self) -> bool:
        """Test API connectivity and authentication."""
        try:
            url = f"{self.BASE_URL}/api/v3/account"
            params = {
                "timestamp": int(time.time() * 1000),
                "recvWindow": 5000
            }
            params["signature"] = self._generate_signature(params)
            headers = self._get_headers()
            session = await self._get_session()

            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                if "code" in data and data.get("code", 0) < 0:
                    logger.error(f"Binance connectivity test failed: {data}")
                    return False
                logger.info("✅ Binance API connected (account verified)")
                return True
        except Exception as e:
            logger.error(f"Binance connectivity test error: {e}")
            return False
