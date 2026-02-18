#!/usr/bin/env python3
"""
KuCoin REST API client for authenticated operations.
Implements order placement, cancellation, balance queries, and withdrawals.
"""
import time
import hmac
import hashlib
import base64
import json
import socket
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base_client import BaseRESTClient

logger = logging.getLogger("kucoin_rest")


class KuCoinRESTClient(BaseRESTClient):
    """KuCoin exchange REST API client."""
    
    BASE_URL = "https://api.kucoin.com"
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str):
        super().__init__(api_key, api_secret, "KuCoin")
        self.passphrase = passphrase
        self._session: Optional[aiohttp.ClientSession] = None
    
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
    
    def _generate_signature(self, timestamp: str, method: str, endpoint: str, body: str = "") -> str:
        """Generate HMAC SHA256 signature for KuCoin API."""
        str_to_sign = timestamp + method.upper() + endpoint + body
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                str_to_sign.encode('utf-8'),
                hashlib.sha256
            ).digest()
        )
        return signature.decode('utf-8')
    
    def _get_headers(self, method: str, endpoint: str, body: str = "") -> Dict[str, str]:
        """Get authenticated headers for KuCoin API."""
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp, method, endpoint, body)
        
        # Encrypt passphrase
        passphrase_signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                self.passphrase.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return {
            "KC-API-KEY": self.api_key,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-PASSPHRASE": passphrase_signature,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }
    
    def normalize_symbol(self, symbol: str) -> str:
        """KuCoin uses BTC-USDT format already."""
        return symbol
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """Place an order on KuCoin."""
        endpoint = "/api/v1/orders"
        url = f"{self.BASE_URL}{endpoint}"
        
        order_data = {
            "clientOid": f"{int(time.time() * 1000)}",
            "side": side.lower(),  # buy or sell
            "symbol": self.normalize_symbol(symbol),
            "type": "market" if order_type == "market" else "limit",
        }
        
        if order_type == "market":
            # Market orders use 'funds' for buy, 'size' for sell
            if side.lower() == "buy":
                order_data["funds"] = str(quantity * price) if price else str(quantity)
            else:
                order_data["size"] = str(quantity)
        else:
            order_data["price"] = str(price)
            order_data["size"] = str(quantity)
            order_data["timeInForce"] = time_in_force
        
        body = json.dumps(order_data)
        headers = self._get_headers("POST", endpoint, body)
        
        session = await self._get_session()
        async with session.post(url, data=body, headers=headers) as resp:
            data = await resp.json()
            if data.get("code") != "200000":
                raise Exception(f"KuCoin order failed: {data}")
            return data.get("data", {})
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order on KuCoin."""
        endpoint = f"/api/v1/orders/{order_id}"
        url = f"{self.BASE_URL}{endpoint}"
        
        headers = self._get_headers("DELETE", endpoint)
        
        session = await self._get_session()
        async with session.delete(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("code") != "200000":
                raise Exception(f"KuCoin cancel failed: {data}")
            return data.get("data", {})
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get order status from KuCoin."""
        endpoint = f"/api/v1/orders/{order_id}"
        url = f"{self.BASE_URL}{endpoint}"
        
        headers = self._get_headers("GET", endpoint)
        
        session = await self._get_session()
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("code") != "200000":
                raise Exception(f"KuCoin get order failed: {data}")
            return data.get("data", {})
    
    async def get_balance(self) -> Dict[str, float]:
        """Get account balances from KuCoin."""
        endpoint = "/api/v1/accounts"
        url = f"{self.BASE_URL}{endpoint}"
        
        headers = self._get_headers("GET", endpoint)
        
        session = await self._get_session()
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("code") != "200000":
                raise Exception(f"KuCoin get balance failed: {data}")
            
            accounts = data.get("data", [])
            balances = {}
            
            # Aggregate balances by currency (type=trade for spot)
            for account in accounts:
                if account.get("type") == "trade":
                    currency = account.get("currency")
                    available = float(account.get("available", 0))
                    if currency:
                        balances[currency] = balances.get(currency, 0) + available
            
            return balances
    
    async def withdraw(
        self,
        currency: str,
        amount: float,
        address: str,
        network: str = "TRC20",
        memo: Optional[str] = None
    ) -> Dict[str, Any]:
        """Initiate a withdrawal on KuCoin."""
        endpoint = "/api/v1/withdrawals"
        url = f"{self.BASE_URL}{endpoint}"
        
        withdrawal_data = {
            "currency": currency,
            "address": address,
            "amount": amount,
            "chain": network
        }
        
        if memo:
            withdrawal_data["memo"] = memo
        
        body = json.dumps(withdrawal_data)
        headers = self._get_headers("POST", endpoint, body)
        
        session = await self._get_session()
        async with session.post(url, data=body, headers=headers) as resp:
            data = await resp.json()
            if data.get("code") != "200000":
                raise Exception(f"KuCoin withdrawal failed: {data}")
            return data.get("data", {})
    
    async def get_deposit_address(self, currency: str) -> dict:
        """
        Get deposit address for a specific currency.
        
        Args:
            currency: Currency symbol (e.g., 'USDT', 'BTC')
            
        Returns:
            dict: Deposit address information
        """
        try:
            endpoint = f"/api/v1/deposit-addresses"
            url = f"{self.BASE_URL}{endpoint}"
            params = {"currency": currency}
            
            headers = self._get_headers("GET", endpoint)
            
            session = await self._get_session()
            async with session.get(url, headers=headers, params=params) as resp:
                data = await resp.json()
                if data.get("code") != "200000":
                    logger.error(f"KuCoin get deposit address failed: {data}")
                    return {}
                return data.get('data', {})
        except Exception as e:
            logger.error(f"Error getting deposit address for {currency}: {e}")
            return {}
    
    async def get_trading_pairs(self) -> list:
        """
        Get all available trading pairs.
        
        Returns:
            list: List of trading pair information
        """
        try:
            endpoint = "/api/v1/symbols"
            url = f"{self.BASE_URL}{endpoint}"
            
            headers = self._get_headers("GET", endpoint)
            
            session = await self._get_session()
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                if data.get("code") != "200000":
                    logger.error(f"KuCoin get trading pairs failed: {data}")
                    return []
                return data.get('data', [])
        except Exception as e:
            logger.error(f"Error getting trading pairs: {e}")
            return []
