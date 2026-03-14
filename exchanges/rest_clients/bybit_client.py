#!/usr/bin/env python3
"""
Bybit REST API client for authenticated operations.
Implements order placement, cancellation, balance queries, and withdrawals.
"""
import time
import hmac
import hashlib
import json
import math
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
        self._time_offset_ms: int = 0  # Server time offset (ms)

    def _synced_ts(self) -> str:
        """Get server-synced timestamp in milliseconds."""
        return str(int(time.time() * 1000) + self._time_offset_ms)

    async def sync_server_time(self):
        """Sync local clock with Bybit server time."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.BASE_URL}/v5/market/time") as resp:
                data = await self._check_response(resp)
                server_time = int(data.get("result", {}).get("timeNano", "0")) // 1_000_000
                if server_time > 0:
                    self._time_offset_ms = server_time - int(time.time() * 1000)
                    logger.info(f"Bybit time sync: offset={self._time_offset_ms}ms")
        except Exception as e:
            logger.warning(f"Bybit time sync failed: {e}")
    
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
    
    async def _check_response(self, resp: aiohttp.ClientResponse) -> dict:
        """Check HTTP status before parsing JSON. Raises on non-200 with clear error."""
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Bybit HTTP {resp.status}: {text[:200]}")
        return await resp.json()
    
    def _generate_signature(self, timestamp: str, query_string: str) -> str:
        """Generate HMAC SHA256 signature for Bybit v5 API.
        
        Bybit v5 signature = HMAC_SHA256(timestamp + api_key + recv_window + query_string)
        """
        param_str = timestamp + self.api_key + str(self.recv_window) + query_string
        return hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_auth_headers(self, query_string: str = "") -> Dict[str, str]:
        """Get authenticated headers for Bybit v5 API.
        
        Bybit v5 uses X-BAPI-* headers for authentication (NOT query params).
        """
        timestamp = self._synced_ts()
        signature = self._generate_signature(timestamp, query_string)
        return {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": str(self.recv_window),
        }
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert BTC-USDT to BTCUSDT."""
        return symbol.replace("-", "")
    
    BYBIT_QTY_MAX_DECIMALS = 8

    @staticmethod
    def _truncate_qty(quantity: float) -> str:
        """Truncate quantity to max decimal places and format as clean string.

        Prevents 'Order quantity has too many decimals' (retCode 170137).
        Python float arithmetic can produce 5.890000000000001 from
        math.floor(5.89/0.01)*0.01 — this cleans it.
        """
        factor = 10 ** BybitRESTClient.BYBIT_QTY_MAX_DECIMALS
        truncated = math.floor(quantity * factor) / factor
        formatted = f"{truncated:.{BybitRESTClient.BYBIT_QTY_MAX_DECIMALS}f}".rstrip('0').rstrip('.')
        # Safety: ensure at least "0" is returned (not empty string)
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
        """Place an order on Bybit using v5 API with header authentication."""
        url = f"{self.BASE_URL}/v5/order/create"
        
        body = {
            "category": "spot",
            "symbol": self.normalize_symbol(symbol),
            "side": side.capitalize(),
            "orderType": "Market" if order_type == "market" else "Limit",
            "qty": self._truncate_qty(quantity),
        }
        
        if order_type == "market" and side.lower() == "buy" and price:
            # For market buy, send USDT amount (quoteCoin) to avoid minimum notional issues
            usdt_amount = round(quantity * price, 2)
            if usdt_amount < 5.0:
                usdt_amount = 5.0  # Bybit minimum for most spot pairs
            body["qty"] = str(usdt_amount)
            body["marketUnit"] = "quoteCoin"
        
        if order_type == "limit" and price:
            body["price"] = str(round(price, 8))
            body["timeInForce"] = time_in_force
        
        body_str = json.dumps(body)
        headers = self._get_auth_headers(body_str)
        headers["Content-Type"] = "application/json"
        
        session = await self._get_session()
        async with session.post(url, data=body_str, headers=headers) as resp:
            data = await self._check_response(resp)
            if data.get("retCode") != 0:
                raise Exception(f"Bybit order failed: {data}")
            return data.get("result", {})
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Cancel an order on Bybit using v5 API."""
        url = f"{self.BASE_URL}/v5/order/cancel"
        
        body = {
            "category": "spot",
            "symbol": self.normalize_symbol(symbol),
            "orderId": order_id,
        }
        
        body_str = json.dumps(body)
        headers = self._get_auth_headers(body_str)
        headers["Content-Type"] = "application/json"
        
        session = await self._get_session()
        async with session.post(url, data=body_str, headers=headers) as resp:
            data = await self._check_response(resp)
            if data.get("retCode") != 0:
                raise Exception(f"Bybit cancel failed: {data}")
            return data.get("result", {})
    
    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Get order status from Bybit using v5 API."""
        url = f"{self.BASE_URL}/v5/order/realtime"
        
        query_string = f"category=spot&symbol={self.normalize_symbol(symbol)}&orderId={order_id}"
        headers = self._get_auth_headers(query_string)
        
        session = await self._get_session()
        async with session.get(f"{url}?{query_string}", headers=headers) as resp:
            data = await self._check_response(resp)
            if data.get("retCode") != 0:
                raise Exception(f"Bybit get order failed: {data}")
            return data.get("result", {})
    
    async def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """Get account balances from Bybit using v5 API with header authentication.
        
        Tries UNIFIED account first (new unified trading accounts).
        Falls back to SPOT account if UNIFIED returns empty balances
        (user hasn't upgraded to unified trading account yet).
        """
        url = f"{self.BASE_URL}/v5/account/wallet-balance"
        
        # Try UNIFIED first (covers spot + derivatives in unified accounts)
        for account_type in ["UNIFIED", "SPOT"]:
            query_string = f"accountType={account_type}"
            headers = self._get_auth_headers(query_string)
            
            session = await self._get_session()
            async with session.get(f"{url}?{query_string}", headers=headers) as resp:
                data = await self._check_response(resp)
                if data.get("retCode") != 0:
                    logger.debug(f"Bybit {account_type} balance query failed: {data.get('retMsg', '')}")
                    continue
                
                # Parse balances
                balances = {}
                result = data.get("result", {})
                for item in result.get("list", []):
                    for coin in item.get("coin", []):
                        coin_name = coin.get("coin")
                        # Try multiple balance fields — Bybit uses different field names
                        # for UNIFIED vs SPOT accounts
                        available = float(
                            coin.get("availableToWithdraw") or
                            coin.get("free") or
                            coin.get("walletBalance") or 0
                        )
                        if available > 0:
                            balances[coin_name] = available
                
                if balances:
                    logger.info(f"✅ Bybit balance loaded from {account_type} account: {len(balances)} coins")
                    if currency:
                        return {currency: balances.get(currency, 0.0)}
                    return balances
        
        # Both account types returned empty
        logger.warning("⚠️  Bybit: no balances found in UNIFIED or SPOT accounts")
        if currency:
            return {currency: 0.0}
        return {}
    
    async def get_trading_pairs(self) -> List[Dict[str, Any]]:
        """Get trading pairs from Bybit."""
        url = f"{self.BASE_URL}/v5/market/instruments-info"
        
        params = {"category": "spot"}
        
        session = await self._get_session()
        async with session.get(url, params=params) as resp:
            data = await self._check_response(resp)
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
        """Withdraw funds from Bybit using v5 API."""
        url = f"{self.BASE_URL}/v5/asset/withdraw/create"
        
        body = {
            "coin": currency,
            "amount": str(amount),
            "address": address,
        }
        
        if network:
            body["chain"] = network
        if memo:
            body["tag"] = memo
        
        body_str = json.dumps(body)
        headers = self._get_auth_headers(body_str)
        headers["Content-Type"] = "application/json"
        
        session = await self._get_session()
        async with session.post(url, data=body_str, headers=headers) as resp:
            data = await self._check_response(resp)
            if data.get("retCode") != 0:
                raise Exception(f"Bybit withdraw failed: {data}")
            return data.get("result", {})
    
    async def get_deposit_address(self, currency: str, network: Optional[str] = None) -> Dict[str, str]:
        """Get deposit address from Bybit using v5 API."""
        url = f"{self.BASE_URL}/v5/asset/deposit/query-address"
        
        query_string = f"coin={currency}"
        if network:
            query_string += f"&chain={network}"
        
        headers = self._get_auth_headers(query_string)
        
        session = await self._get_session()
        async with session.get(f"{url}?{query_string}", headers=headers) as resp:
            data = await self._check_response(resp)
            if data.get("retCode") != 0:
                raise Exception(f"Bybit get deposit address failed: {data}")
            
            result = data.get("result", {})
            return {
                "address": result.get("address", ""),
                "memo": result.get("tag", "")
            }
