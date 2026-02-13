#!/usr/bin/env python3
"""
HTX (Huobi) REST API client for authenticated operations.
Implements order placement, cancellation, balance queries, and withdrawals.
"""
import time
import hmac
import hashlib
import base64
import urllib.parse
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base_client import BaseRESTClient

logger = logging.getLogger("htx_rest")


class HTXRESTClient(BaseRESTClient):
    """HTX (Huobi) exchange REST API client."""
    
    BASE_URL = "https://api.huobi.pro"
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret, "HTX")
        self._session: Optional[aiohttp.ClientSession] = None
        self._account_id: Optional[str] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _generate_signature(self, method: str, host: str, path: str, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for HTX API."""
        sorted_params = sorted(params.items())
        param_str = "&".join([f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_params])
        
        payload = f"{method.upper()}\n{host}\n{path}\n{param_str}"
        
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return signature
    
    def _get_common_params(self) -> Dict[str, Any]:
        """Get common parameters for HTX API requests."""
        return {
            "AccessKeyId": self.api_key,
            "SignatureMethod": "HmacSHA256",
            "SignatureVersion": "2",
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        }
    
    async def _get_account_id(self) -> str:
        """Get spot account ID (cached)."""
        if self._account_id:
            return self._account_id
        
        path = "/v1/account/accounts"
        params = self._get_common_params()
        params["Signature"] = self._generate_signature("GET", "api.huobi.pro", path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            if data.get("status") != "ok":
                raise Exception(f"HTX get account failed: {data}")
            
            # Find spot account
            for account in data.get("data", []):
                if account.get("type") == "spot":
                    self._account_id = str(account.get("id"))
                    return self._account_id
            
            raise Exception("HTX spot account not found")
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert BTC-USDT to btcusdt (lowercase, no hyphen)."""
        return symbol.replace("-", "").lower()
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """Place an order on HTX."""
        account_id = await self._get_account_id()
        
        path = "/v1/order/orders/place"
        
        order_data = {
            "account-id": account_id,
            "symbol": self.normalize_symbol(symbol),
            "type": f"{side.lower()}-{order_type}",  # e.g., buy-limit, sell-market
            "amount": str(quantity)
        }
        
        if order_type == "limit" and price:
            order_data["price"] = str(price)
        
        # Add authentication
        params = self._get_common_params()
        params["Signature"] = self._generate_signature("POST", "api.huobi.pro", path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        # HTX wants params in URL and data in body
        async with session.post(url, params=params, json=order_data) as resp:
            data = await resp.json()
            if data.get("status") != "ok":
                raise Exception(f"HTX order failed: {data}")
            return {"orderId": data.get("data")}
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order on HTX."""
        path = f"/v1/order/orders/{order_id}/submitcancel"
        
        params = self._get_common_params()
        params["Signature"] = self._generate_signature("POST", "api.huobi.pro", path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        async with session.post(url, params=params) as resp:
            data = await resp.json()
            if data.get("status") != "ok":
                raise Exception(f"HTX cancel failed: {data}")
            return data.get("data", {})
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status from HTX."""
        path = f"/v1/order/orders/{order_id}"
        
        params = self._get_common_params()
        params["Signature"] = self._generate_signature("GET", "api.huobi.pro", path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            if data.get("status") != "ok":
                raise Exception(f"HTX get order failed: {data}")
            return data.get("data", {})
    
    async def get_balance(self) -> Dict[str, float]:
        """Get account balances from HTX."""
        account_id = await self._get_account_id()
        
        path = f"/v1/account/accounts/{account_id}/balance"
        
        params = self._get_common_params()
        params["Signature"] = self._generate_signature("GET", "api.huobi.pro", path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            if data.get("status") != "ok":
                raise Exception(f"HTX get balance failed: {data}")
            
            balances = {}
            for item in data.get("data", {}).get("list", []):
                if item.get("type") == "trade":  # Available balance
                    currency = item.get("currency", "").upper()
                    balance = float(item.get("balance", 0))
                    if currency:
                        balances[currency] = balance
            
            return balances
    
    async def withdraw(
        self,
        currency: str,
        amount: float,
        address: str,
        network: str = "trc20",
        memo: Optional[str] = None
    ) -> Dict[str, Any]:
        """Initiate a withdrawal on HTX."""
        path = "/v1/dw/withdraw/api/create"
        
        withdrawal_data = {
            "address": address,
            "amount": amount,
            "currency": currency.lower(),
            "chain": network
        }
        
        if memo:
            withdrawal_data["addr-tag"] = memo
        
        params = self._get_common_params()
        params["Signature"] = self._generate_signature("POST", "api.huobi.pro", path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        async with session.post(url, params=params, json=withdrawal_data) as resp:
            data = await resp.json()
            if data.get("status") != "ok":
                raise Exception(f"HTX withdrawal failed: {data}")
            return data.get("data", {})
