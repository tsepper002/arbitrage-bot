#!/usr/bin/env python3
"""
MEXC REST API client for authenticated operations.
Implements order placement, cancellation, balance queries, and withdrawals.
Note: MEXC has 0% maker fees - prioritize limit orders!
"""
import time
import hmac
import hashlib
import urllib.parse
import socket
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base_client import BaseRESTClient

logger = logging.getLogger("mexc_rest")


class MEXCRESTClient(BaseRESTClient):
    """MEXC exchange REST API client."""
    
    BASE_URL = "https://api.mexc.com"
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret, "MEXC")
        self._session: Optional[aiohttp.ClientSession] = None
        self._time_offset_ms: int = 0  # Server time offset (ms)

    def _synced_ts(self) -> int:
        """Get server-synced timestamp in milliseconds."""
        return int(time.time() * 1000) + self._time_offset_ms

    async def sync_server_time(self):
        """Sync local clock with MEXC server time."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.BASE_URL}/api/v3/time") as resp:
                data = await resp.json()
                server_time = int(data.get("serverTime", 0))
                if server_time > 0:
                    self._time_offset_ms = server_time - int(time.time() * 1000)
                    logger.info(f"MEXC time sync: offset={self._time_offset_ms}ms")
        except Exception as e:
            logger.warning(f"MEXC time sync failed: {e}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            # Use IPv4 + ThreadedResolver to avoid DNS resolution issues
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
        """Generate HMAC SHA256 signature for MEXC API."""
        # Sort parameters and create query string
        sorted_params = sorted(params.items())
        param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests."""
        return {
            "Content-Type": "application/json",
            "X-MEXC-APIKEY": self.api_key
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
        """
        Place an order on MEXC.
        Note: MEXC has 0% maker fees - prefer limit orders!
        """
        path = "/api/v3/order"
        url = f"{self.BASE_URL}{path}"
        
        params = {
            "symbol": self.normalize_symbol(symbol),
            "side": side.upper(),  # BUY or SELL
            "type": "MARKET" if order_type == "market" else "LIMIT",
            "quantity": str(quantity),
            "timestamp": str(self._synced_ts())
        }
        
        if order_type == "limit" and price:
            params["price"] = str(price)
            params["timeInForce"] = time_in_force
        elif order_type == "market" and side.upper() == "BUY" and price:
            # MEXC market buy can use quoteOrderQty (USDT amount) instead of quantity
            params["quoteOrderQty"] = str(round(float(params["quantity"]) * price, 2))
            del params["quantity"]
        
        # Add signature
        params["signature"] = self._generate_signature(params)
        
        headers = self._get_headers()
        session = await self._get_session()
        
        async with session.post(url, params=params, headers=headers) as resp:
            data = await resp.json()
            
            # MEXC returns different structures
            if "code" in data and data["code"] != 200:
                raise Exception(f"MEXC order failed: {data}")
            
            return data
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order on MEXC.
        Note: MEXC requires symbol for cancellation.
        """
        path = "/api/v3/order"
        url = f"{self.BASE_URL}{path}"
        
        params = {
            "symbol": self.normalize_symbol(symbol),
            "orderId": str(order_id),
            "timestamp": str(self._synced_ts())
        }
        
        params["signature"] = self._generate_signature(params)
        
        headers = self._get_headers()
        session = await self._get_session()
        
        async with session.delete(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if "code" in data and data["code"] != 200:
                raise Exception(f"MEXC cancel failed: {data}")
            return data
    
    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Get order status from MEXC.
        Note: MEXC requires symbol for order lookup.
        """
        path = "/api/v3/order"
        url = f"{self.BASE_URL}{path}"
        
        params = {
            "symbol": self.normalize_symbol(symbol),
            "orderId": str(order_id),
            "timestamp": str(self._synced_ts())
        }
        
        params["signature"] = self._generate_signature(params)
        
        headers = self._get_headers()
        session = await self._get_session()
        
        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if "code" in data and data["code"] != 200:
                raise Exception(f"MEXC get order failed: {data}")
            return data
    
    async def get_balance(self) -> Dict[str, float]:
        """Get account balances from MEXC."""
        path = "/api/v3/account"
        url = f"{self.BASE_URL}{path}"
        
        params = {
            "timestamp": str(self._synced_ts())
        }
        
        params["signature"] = self._generate_signature(params)
        
        headers = self._get_headers()
        session = await self._get_session()
        
        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()
            
            if "code" in data and data["code"] != 200:
                raise Exception(f"MEXC get balance failed: {data}")
            
            balances = {}
            for item in data.get("balances", []):
                asset = item.get("asset")
                free = float(item.get("free", 0))
                if asset and free > 0:
                    balances[asset] = free
            
            return balances
    
    async def withdraw(
        self,
        currency: str,
        amount: float,
        address: str,
        network: str = "TRX",
        memo: Optional[str] = None
    ) -> Dict[str, Any]:
        """Initiate a withdrawal on MEXC."""
        path = "/api/v3/capital/withdraw/apply"
        url = f"{self.BASE_URL}{path}"
        
        params = {
            "coin": currency,
            "address": address,
            "amount": str(amount),
            "network": network,
            "timestamp": str(self._synced_ts())
        }
        
        if memo:
            params["addressTag"] = memo
        
        params["signature"] = self._generate_signature(params)
        
        headers = self._get_headers()
        session = await self._get_session()
        
        async with session.post(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if "code" in data and data["code"] != 200:
                raise Exception(f"MEXC withdrawal failed: {data}")
            return data
    
    async def get_deposit_address(self, currency: str) -> dict:
        """
        Get deposit address for a specific currency on MEXC.
        
        Args:
            currency: Currency symbol (e.g., 'USDT', 'BTC')
            
        Returns:
            dict: Deposit address information
        """
        try:
            path = "/api/v3/capital/deposit/address"
            url = f"{self.BASE_URL}{path}"
            
            params = {
                "coin": currency,
                "timestamp": str(self._synced_ts())
            }
            
            params["signature"] = self._generate_signature(params)
            
            headers = self._get_headers()
            session = await self._get_session()
            
            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                if "code" in data and data["code"] == 200:
                    return data
                else:
                    logger.error(f"Error getting MEXC deposit address for {currency}: {data}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting deposit address for {currency}: {e}")
            return {}
    
    async def get_trading_pairs(self) -> list:
        """
        Get all available trading pairs on MEXC.
        
        Returns:
            list: List of trading pair information
        """
        try:
            path = "/api/v3/exchangeInfo"
            url = f"{self.BASE_URL}{path}"
            session = await self._get_session()
            
            async with session.get(url) as resp:
                data = await resp.json()
                if "symbols" in data:
                    return data.get("symbols", [])
                else:
                    logger.error(f"Error getting MEXC trading pairs: {data}")
                    return []
        except Exception as e:
            logger.error(f"Error getting trading pairs: {e}")
            return []
