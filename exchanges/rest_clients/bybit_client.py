#!/usr/bin/env python3
"""
Bybit REST API client for authenticated operations.
Implements order placement, cancellation, balance queries, and withdrawals.
"""
import time
import hmac
import hashlib
import socket
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base_client import BaseRESTClient

logger = logging.getLogger("bybit_rest")


class BybitRESTClient(BaseRESTClient):
    """Bybit exchange REST API client."""
    
    BASE_URL = "https://api.bybit.com"
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret, "Bybit")
        self.recv_window = 5000  # 5 seconds
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session (reuse for efficiency)."""
        if self._session is None or self._session.closed:
            # Use IPv4 + ThreadedResolver to avoid DNS resolution issues
            connector = aiohttp.TCPConnector(
                family=socket.AF_INET,
                resolver=aiohttp.ThreadedResolver()  # Use system DNS instead of aiodns
            )
            timeout = aiohttp.ClientTimeout(total=30, sock_connect=10)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for Bybit API."""
        param_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
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
            "X-BAPI-API-KEY": self.api_key,
        }
    
    def _add_auth_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add authentication parameters."""
        params["api_key"] = self.api_key
        params["timestamp"] = str(int(time.time() * 1000))
        params["recv_window"] = str(self.recv_window)
        params["sign"] = self._generate_signature(params)
        return params
    
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
        """Place an order on Bybit."""
        url = f"{self.BASE_URL}/v5/order/create"
        
        params = {
            "category": "spot",
            "symbol": self.normalize_symbol(symbol),
            "side": side.capitalize(),  # Buy or Sell
            "orderType": "Market" if order_type == "market" else "Limit",
            "qty": str(quantity),
        }
        
        if order_type == "limit" and price:
            params["price"] = str(price)
            params["timeInForce"] = time_in_force
        
        headers = self._get_headers()
        params = self._add_auth_params(params)
        
        session = await self._get_session()
        async with session.post(url, json=params, headers=headers) as resp:
            data = await resp.json()
            if data.get("retCode") != 0:
                raise Exception(f"Bybit order failed: {data}")
            return data.get("result", {})
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancel an order on Bybit."""
        url = f"{self.BASE_URL}/v5/order/cancel"
        
        params = {
            "category": "spot",
            "symbol": self.normalize_symbol(symbol),
            "orderId": order_id,
        }
        
        headers = self._get_headers()
        params = self._add_auth_params(params)
        
        session = await self._get_session()
        async with session.post(url, json=params, headers=headers) as resp:
            data = await resp.json()
            if data.get("retCode") != 0:
                raise Exception(f"Bybit cancel failed: {data}")
            return data.get("result", {})
    
    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Get order status from Bybit."""
        url = f"{self.BASE_URL}/v5/order/realtime"
        
        params = {
            "category": "spot",
            "symbol": self.normalize_symbol(symbol),
            "orderId": order_id,
        }
        
        headers = self._get_headers()
        params = self._add_auth_params(params)
        
        session = await self._get_session()
        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if data.get("retCode") != 0:
                raise Exception(f"Bybit get order failed: {data}")
            return data.get("result", {})
    
    async def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """Get account balances from Bybit."""
        url = f"{self.BASE_URL}/v5/account/wallet-balance"
        
        params = {
            "accountType": "SPOT",
        }
        
        headers = self._get_headers()
        params = self._add_auth_params(params)
        
        session = await self._get_session()
        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if data.get("retCode") != 0:
                raise Exception(f"Bybit get balance failed: {data}")
            
            # Parse balances
            balances = {}
            result = data.get("result", {})
            for item in result.get("list", []):
                for coin in item.get("coin", []):
                    coin_name = coin.get("coin")
                    available = float(coin.get("availableToWithdraw", 0))
                    if available > 0:
                        balances[coin_name] = available
            
            if currency:
                return {currency: balances.get(currency, 0.0)}
            return balances
    
    async def get_trading_pairs(self) -> List[Dict[str, Any]]:
        """Get trading pairs from Bybit."""
        url = f"{self.BASE_URL}/v5/market/instruments-info"
        
        params = {"category": "spot"}
        
        session = await self._get_session()
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            if data.get("retCode") != 0:
                raise Exception(f"Bybit get pairs failed: {data}")
            return data.get("result", {}).get("list", [])
    
    async def withdraw(
        self,
        currency: str,
        amount: float,
        address: str,
        network: Optional[str] = None,
        memo: Optional[str] = None
    ) -> Dict[str, Any]:
        """Withdraw funds from Bybit."""
        url = f"{self.BASE_URL}/v5/asset/withdraw/create"
        
        params = {
            "coin": currency,
            "amount": str(amount),
            "address": address,
        }
        
        if network:
            params["chain"] = network
        if memo:
            params["tag"] = memo
        
        headers = self._get_headers()
        params = self._add_auth_params(params)
        
        session = await self._get_session()
        async with session.post(url, json=params, headers=headers) as resp:
            data = await resp.json()
            if data.get("retCode") != 0:
                raise Exception(f"Bybit withdraw failed: {data}")
            return data.get("result", {})
    
    async def get_deposit_address(self, currency: str, network: Optional[str] = None) -> Dict[str, str]:
        """Get deposit address from Bybit."""
        url = f"{self.BASE_URL}/v5/asset/deposit/query-address"
        
        params = {
            "coin": currency,
        }
        
        if network:
            params["chain"] = network
        
        headers = self._get_headers()
        params = self._add_auth_params(params)
        
        session = await self._get_session()
        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if data.get("retCode") != 0:
                raise Exception(f"Bybit get deposit address failed: {data}")
            
            result = data.get("result", {})
            return {
                "address": result.get("address", ""),
                "memo": result.get("tag", "")
            }
