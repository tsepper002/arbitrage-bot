#!/usr/bin/env python3
"""
HTX (Huobi) REST API client with HMAC SHA256 authentication.
API Documentation: https://www.htx.com/en-us/opend/newApiPages/
"""
import os
import logging
import json
import base64
import hashlib
from typing import Dict, Optional, Any
from urllib.parse import urlencode, urlparse
from datetime import datetime
from .base_rest import BaseRestClient

logger = logging.getLogger(__name__)


class HTXRestClient(BaseRestClient):
    """
    HTX (formerly Huobi) REST API client.
    Implements canonical request format with HMAC SHA256 authentication.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize HTX REST client.
        
        Args:
            api_key: HTX API key (defaults to HTX_API_KEY env var)
            api_secret: HTX API secret (defaults to HTX_API_SECRET env var)
        """
        api_key = api_key or os.getenv('HTX_API_KEY')
        api_secret = api_secret or os.getenv('HTX_API_SECRET')
        super().__init__(api_key, api_secret)
        self._account_id = None
        
    def _get_base_url(self) -> str:
        """Return HTX API base URL."""
        return "https://api.huobi.pro"
    
    def _sign_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     body: Optional[Dict] = None) -> Dict[str, str]:
        """
        Generate HTX API signature using canonical request format.
        
        Signature includes:
        - Method
        - Host
        - Path
        - Sorted query parameters
        
        Returns:
            Headers for authenticated request (signature goes in params)
        """
        # Parse URL to get host
        parsed_url = urlparse(self._get_base_url())
        host = parsed_url.hostname
        
        # Get timestamp in UTC
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        
        # Build parameters
        sign_params = {
            'AccessKeyId': self.api_key,
            'SignatureMethod': 'HmacSHA256',
            'SignatureVersion': '2',
            'Timestamp': timestamp
        }
        
        if params:
            sign_params.update(params)
        
        # Sort parameters
        sorted_params = sorted(sign_params.items())
        encoded_params = urlencode(sorted_params)
        
        # Create canonical request
        payload = f"{method}\n{host}\n{endpoint}\n{encoded_params}"
        
        # Sign with HMAC SHA256
        signature = base64.b64encode(
            hashlib.sha256(
                self.api_secret.encode('utf-8') + 
                payload.encode('utf-8')
            ).digest()
        ).decode()
        
        sign_params['Signature'] = signature
        
        # Return empty headers dict - signature goes in query params for HTX
        return {}
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                body: Optional[Dict] = None, signed: bool = False) -> Dict[str, Any]:
        """
        Override request method to handle HTX-specific signature in params.
        """
        url = self._get_base_url() + endpoint
        
        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API credentials required for signed requests")
            
            # Get timestamp
            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
            
            # Build signature params
            parsed_url = urlparse(url)
            host = parsed_url.hostname
            
            sign_params = {
                'AccessKeyId': self.api_key,
                'SignatureMethod': 'HmacSHA256',
                'SignatureVersion': '2',
                'Timestamp': timestamp
            }
            
            if params:
                sign_params.update(params)
            
            # Sort and encode
            sorted_params = sorted(sign_params.items())
            encoded_params = urlencode(sorted_params)
            
            # Create signature payload
            payload = f"{method}\n{host}\n{endpoint}\n{encoded_params}"
            
            # Generate signature
            signature = base64.b64encode(
                hashlib.sha256(
                    self.api_secret.encode('utf-8') + 
                    payload.encode('utf-8')
                ).digest()
            ).decode()
            
            sign_params['Signature'] = signature
            params = sign_params
        
        try:
            if method == 'GET':
                response = self.session.get(url, params=params, timeout=10)
            elif method == 'POST':
                response = self.session.post(url, params=params, json=body, timeout=10)
            elif method == 'DELETE':
                response = self.session.delete(url, params=params, json=body, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"HTX request failed: {method} {url} - {e}")
            raise
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to HTX format (btcusdt - lowercase)."""
        return symbol.replace('-', '').replace('_', '').lower()
    
    def _get_account_id(self) -> str:
        """Get account ID (required for balance and trading operations)."""
        if self._account_id:
            return self._account_id
        
        try:
            response = self._request('GET', '/v1/account/accounts', signed=True)
            
            if response.get('status') != 'ok':
                raise Exception(f"Failed to get account: {response}")
            
            # Get spot account
            accounts = response.get('data', [])
            for account in accounts:
                if account.get('type') == 'spot':
                    self._account_id = str(account.get('id'))
                    return self._account_id
            
            raise Exception("No spot account found")
            
        except Exception as e:
            logger.error(f"Failed to get HTX account ID: {e}")
            raise
    
    def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """
        Get account balance from spot account.
        
        Args:
            currency: Specific currency to query (e.g., 'BTC', 'USDT')
            
        Returns:
            Dictionary of currency -> available balance
            
        Example:
            {'BTC': 0.5, 'USDT': 10000.0}
        """
        try:
            account_id = self._get_account_id()
            
            response = self._request('GET', f'/v1/account/accounts/{account_id}/balance',
                                   signed=True)
            
            if response.get('status') != 'ok':
                logger.error(f"HTX balance error: {response}")
                return {}
            
            balances = {}
            balance_list = response.get('data', {}).get('list', [])
            
            for item in balance_list:
                if item.get('type') == 'trade':  # Available balance
                    curr = item.get('currency', '').upper()
                    balance = float(item.get('balance', 0))
                    
                    if currency and curr != currency.upper():
                        continue
                    
                    if balance > 0:
                        balances[curr] = balance
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get HTX balance: {e}")
            return {}
    
    def place_order(self, symbol: str, side: str, order_type: str,
                   quantity: float, price: Optional[float] = None,
                   time_in_force: str = "GTC") -> Dict[str, Any]:
        """
        Place order on HTX.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT" or "btcusdt")
            side: "buy" or "sell"
            order_type: "market" or "limit"
            quantity: Order quantity
            price: Limit price (required for limit orders)
            time_in_force: Not used by HTX (kept for API consistency)
            
        Returns:
            Order response with order ID
        """
        try:
            account_id = self._get_account_id()
            normalized_symbol = self._normalize_symbol(symbol)
            
            # HTX uses combined type: buy-limit, sell-market, etc.
            htx_type = f"{side.lower()}-{order_type.lower()}"
            
            body = {
                'account-id': account_id,
                'symbol': normalized_symbol,
                'type': htx_type,
                'amount': str(quantity)
            }
            
            if order_type.lower() == 'limit':
                if price is None:
                    raise ValueError("Price required for limit orders")
                body['price'] = str(price)
            
            response = self._request('POST', '/v1/order/orders/place', 
                                   body=body, signed=True)
            
            if response.get('status') != 'ok':
                logger.error(f"HTX order error: {response}")
                raise Exception(f"Order failed: {response.get('err-msg')}")
            
            order_id = response.get('data')
            return {
                'order_id': str(order_id),
                'status': 'submitted',
                'symbol': normalized_symbol,
                'side': side.lower(),
                'type': order_type.lower(),
                'quantity': quantity,
                'price': price
            }
            
        except Exception as e:
            logger.error(f"Failed to place HTX order: {e}")
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an open order on HTX.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair (not used in API but kept for consistency)
            
        Returns:
            Cancellation confirmation
        """
        try:
            response = self._request('POST', f'/v1/order/orders/{order_id}/submitcancel',
                                   signed=True)
            
            if response.get('status') != 'ok':
                logger.error(f"HTX cancel error: {response}")
                raise Exception(f"Cancel failed: {response.get('err-msg')}")
            
            return {
                'order_id': order_id,
                'status': 'cancelled',
                'cancel_result': response.get('data')
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel HTX order: {e}")
            raise
    
    def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Get order status from HTX.
        
        Args:
            order_id: Order ID to query
            symbol: Trading pair (not used in API but kept for consistency)
            
        Returns:
            Order details including status and fill information
        """
        try:
            response = self._request('GET', f'/v1/order/orders/{order_id}', signed=True)
            
            if response.get('status') != 'ok':
                logger.error(f"HTX order query error: {response}")
                return {}
            
            order = response.get('data', {})
            if not order:
                return {}
            
            return {
                'order_id': str(order.get('id')),
                'symbol': order.get('symbol'),
                'side': order.get('type', '').split('-')[0] if '-' in order.get('type', '') else '',
                'type': order.get('type', '').split('-')[1] if '-' in order.get('type', '') else '',
                'status': order.get('state'),
                'quantity': float(order.get('amount', 0)),
                'price': float(order.get('price', 0)),
                'executed_qty': float(order.get('field-amount', 0)),
                'executed_value': float(order.get('field-cash-amount', 0)),
                'fee': float(order.get('field-fees', 0)),
                'created_time': order.get('created-at'),
                'finished_time': order.get('finished-at')
            }
            
        except Exception as e:
            logger.error(f"Failed to get HTX order status: {e}")
            return {}
