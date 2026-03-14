#!/usr/bin/env python3
"""
HTX (Huobi) REST API client for authenticated operations.
Implements order placement, cancellation, balance queries, and withdrawals.
"""
import asyncio
import time
import hmac
import hashlib
import math
import base64
import urllib.parse
import socket
from typing import Dict, Any, Optional, List
import aiohttp
import logging
from .base_client import BaseRESTClient

logger = logging.getLogger("htx_rest")


class HTXRESTClient(BaseRESTClient):
    """HTX (Huobi) exchange REST API client."""
    
    # Try new domain first (api.htx.com), fall back to legacy (api.huobi.pro)
    BASE_URLS = ["https://api.htx.com", "https://api.huobi.pro"]
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret, "HTX")
        self._session: Optional[aiohttp.ClientSession] = None
        self._account_id: Optional[str] = None
        self._active_base_url: str = self.BASE_URLS[0]
        self._active_host: str = "api.htx.com"
        self._time_offset_sec: int = 0  # Server time offset (seconds)

    async def sync_server_time(self):
        """Sync local clock with HTX server time."""
        try:
            session = await self._get_session()
            for base_url in self.BASE_URLS:
                try:
                    local_before = time.time() * 1000
                    async with session.get(f"{base_url}/v1/common/timestamp") as resp:
                        data = await self._check_response(resp)
                        if data.get("status") == "ok":
                            server_time_ms = int(data.get("data", 0))
                            self._time_offset_sec = int((server_time_ms - local_before) / 1000)
                            logger.info(f"HTX time sync: offset={self._time_offset_sec}s")
                            return
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"HTX time sync failed: {e}")
    
    @property
    def BASE_URL(self) -> str:
        return self._active_base_url
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            # Use IPv4 + ThreadedResolver to avoid DNS resolution issues
            connector = aiohttp.TCPConnector(
                family=socket.AF_INET,
                resolver=aiohttp.ThreadedResolver()
            )
            timeout = aiohttp.ClientTimeout(total=10, sock_connect=5)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _check_response(self, resp: aiohttp.ClientResponse) -> dict:
        """Check HTTP status before parsing JSON. Raises on non-200 with clear error."""
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"HTX HTTP {resp.status}: {text[:200]}")
        return await resp.json()
    
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
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + self._time_offset_sec))
        }
    
    async def _get_account_id(self) -> str:
        """Get spot account ID (cached). Tries multiple API domains."""
        if self._account_id:
            return self._account_id
        
        path = "/v1/account/accounts"
        
        for base_url in self.BASE_URLS:
            host = base_url.replace("https://", "")
            try:
                params = self._get_common_params()
                params["Signature"] = self._generate_signature("GET", host, path, params)
                
                url = f"{base_url}{path}"
                session = await self._get_session()
                
                async with session.get(url, params=params) as resp:
                    data = await self._check_response(resp)
                    if data.get("status") != "ok":
                        logger.warning(f"HTX {host} account query failed: {data.get('err-msg', data.get('status', 'unknown'))}")
                        continue
                    
                    # Find spot account
                    for account in data.get("data", []):
                        if account.get("type") == "spot":
                            self._account_id = str(account.get("id"))
                            self._active_base_url = base_url
                            self._active_host = host
                            logger.info(f"HTX: using {host} (account {self._account_id})")
                            return self._account_id
                    
                    logger.warning(f"HTX {host}: spot account not found in response")
            except asyncio.TimeoutError:
                logger.warning(f"HTX {host}: connection timed out")
            except Exception as e:
                logger.warning(f"HTX {host}: {e}")
        
        raise Exception(f"HTX: failed to get account from all domains ({', '.join(self.BASE_URLS)})")
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert BTC-USDT to btcusdt (lowercase, no hyphen)."""
        return symbol.replace("-", "").lower()
    
    HTX_QTY_MAX_DECIMALS = 8

    @staticmethod
    def _truncate_qty(quantity: float) -> str:
        """Format quantity as clean string without floating-point artifacts.

        Prevents floating-point artifacts like 5.890000000000001
        from being sent to HTX API.
        NOTE: round_qty() in exchange_config already floors to step_size,
        so we only need to format cleanly here, not re-floor.
        """
        formatted = f"{quantity:.{HTXRESTClient.HTX_QTY_MAX_DECIMALS}f}"
        if '.' in formatted:
            formatted = formatted.rstrip('0').rstrip('.')
        return formatted if formatted else "0"

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """Place an order on HTX.
        
        For market buy: quantity is base amount, price converts to quote amount.
        HTX buy-market uses 'amount' as QUOTE (USDT) amount.
        """
        account_id = await self._get_account_id()
        
        path = "/v1/order/orders/place"
        
        order_data = {
            "account-id": account_id,
            "symbol": self.normalize_symbol(symbol),
            "type": f"{side.lower()}-{order_type}",  # e.g., buy-limit, sell-market
        }
        
        if order_type == "market" and side.lower() == "buy":
            # HTX buy-market: 'amount' = QUOTE amount (USDT to spend)
            # price MUST be provided by caller for correct conversion
            if price and price > 0:
                usdt_amount = quantity * price
            else:
                raise ValueError(
                    f"HTX market buy requires price for quote conversion. "
                    f"Got quantity={quantity}, price={price}"
                )
            order_data["amount"] = str(round(usdt_amount, 2))
        else:
            order_data["amount"] = self._truncate_qty(quantity)
        
        if order_type == "limit" and price:
            order_data["price"] = str(price)
        
        # Add authentication
        params = self._get_common_params()
        params["Signature"] = self._generate_signature("POST", self._active_host, path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        # HTX wants params in URL and data in body
        async with session.post(url, params=params, json=order_data) as resp:
            data = await self._check_response(resp)
            if data.get("status") != "ok":
                raise Exception(f"HTX order failed: {data}")
            order_id = data.get("data")
            if not order_id:
                raise Exception(f"HTX order succeeded but returned no orderId: {data}")
            return {"orderId": str(order_id)}
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancel an order on HTX. Symbol accepted for interface compatibility but not used (order_id is sufficient)."""
        path = f"/v1/order/orders/{order_id}/submitcancel"
        
        params = self._get_common_params()
        params["Signature"] = self._generate_signature("POST", self._active_host, path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        async with session.post(url, params=params) as resp:
            data = await self._check_response(resp)
            if data.get("status") != "ok":
                raise Exception(f"HTX cancel failed: {data}")
            return data.get("data", {})
    
    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Get order status from HTX. Symbol accepted for interface compatibility but not used."""
        path = f"/v1/order/orders/{order_id}"
        
        params = self._get_common_params()
        params["Signature"] = self._generate_signature("GET", self._active_host, path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        async with session.get(url, params=params) as resp:
            data = await self._check_response(resp)
            if data.get("status") != "ok":
                raise Exception(f"HTX get order failed: {data}")
            return data.get("data", {})
    
    async def get_balance(self) -> Dict[str, float]:
        """Get account balances from HTX."""
        account_id = await self._get_account_id()
        
        path = f"/v1/account/accounts/{account_id}/balance"
        
        params = self._get_common_params()
        params["Signature"] = self._generate_signature("GET", self._active_host, path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        async with session.get(url, params=params) as resp:
            data = await self._check_response(resp)
            if data.get("status") != "ok":
                raise Exception(f"HTX get balance failed: {data}")
            
            balances = {}
            for item in data.get("data", {}).get("list", []):
                if item.get("type") == "trade":  # Available balance
                    currency = item.get("currency", "").upper()
                    try:
                        balance = float(item.get("balance", 0))
                    except (ValueError, TypeError):
                        continue
                    if currency and balance > 0:
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
        params["Signature"] = self._generate_signature("POST", self._active_host, path, params)
        
        url = f"{self.BASE_URL}{path}"
        session = await self._get_session()
        
        async with session.post(url, params=params, json=withdrawal_data) as resp:
            data = await self._check_response(resp)
            if data.get("status") != "ok":
                raise Exception(f"HTX withdrawal failed: {data}")
            return data.get("data", {})
    
    async def get_deposit_address(self, currency: str) -> dict:
        """
        Get deposit address for a specific currency on HTX.
        
        Args:
            currency: Currency symbol (e.g., 'USDT', 'BTC')
            
        Returns:
            dict: Deposit address information
        """
        try:
            path = "/v2/account/deposit/address"
            params = self._get_common_params()
            params["currency"] = currency.lower()
            params["Signature"] = self._generate_signature("GET", self._active_host, path, params)
            
            url = f"{self.BASE_URL}{path}"
            session = await self._get_session()
            
            async with session.get(url, params=params) as resp:
                data = await self._check_response(resp)
                if data.get("status") == "ok" or data.get("code") == 200:
                    return data.get("data", {})
                else:
                    logger.error(f"Error getting HTX deposit address for {currency}: {data}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting deposit address for {currency}: {e}")
            return {}
    
    async def get_trading_pairs(self) -> list:
        """
        Get all available trading pairs on HTX.
        
        Returns:
            list: List of trading pair information
        """
        try:
            path = "/v1/common/symbols"
            url = f"{self.BASE_URL}{path}"
            session = await self._get_session()
            
            async with session.get(url) as resp:
                data = await self._check_response(resp)
                if data.get("status") == "ok":
                    return data.get("data", [])
                else:
                    logger.error(f"Error getting HTX trading pairs: {data}")
                    return []
        except Exception as e:
            logger.error(f"Error getting trading pairs: {e}")
            return []
