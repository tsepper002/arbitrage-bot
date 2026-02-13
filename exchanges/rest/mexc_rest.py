#!/usr/bin/env python3
"""
MEXC REST API client with HMAC SHA256 authentication.
API Documentation: https://mexcdevelop.github.io/apidocs/spot_v3_en/
"""
import os
import logging
import json
from typing import Dict, Optional, Any
from urllib.parse import urlencode
from .base_rest import BaseRestClient

logger = logging.getLogger(__name__)


class MEXCRestClient(BaseRestClient):
    """
    MEXC REST API client.
    Implements HMAC SHA256 authentication similar to Binance API style.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize MEXC REST client.
        
        Args:
            api_key: MEXC API key (defaults to MEXC_API_KEY env var)
            api_secret: MEXC API secret (defaults to MEXC_API_SECRET env var)
        """
        api_key = api_key or os.getenv('MEXC_API_KEY')
        api_secret = api_secret or os.getenv('MEXC_API_SECRET')
        super().__init__(api_key, api_secret)
        
    def _get_base_url(self) -> str:
        """Return MEXC API base URL."""
        return "https://api.mexc.com"
    
    def _sign_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     body: Optional[Dict] = None) -> Dict[str, str]:
        """
        Generate MEXC API signature.
        
        Signature format: HMAC SHA256 of query string including timestamp
        Similar to Binance API authentication.
        
        Returns:
            Headers with API key (signature goes in params)
        """
        # Return API key header, signature will be added to params
        return {
            'X-MEXC-APIKEY': self.api_key
        }
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                body: Optional[Dict] = None, signed: bool = False) -> Dict[str, Any]:
        """
        Override request method to handle MEXC-specific signature in params.
        """
        url = self._get_base_url() + endpoint
        headers = {}
        
        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API credentials required for signed requests")
            
            # Add timestamp to params
            timestamp = str(self._get_timestamp_ms())
            if params is None:
                params = {}
            params['timestamp'] = timestamp
            params['recvWindow'] = '5000'
            
            # Create query string for signature
            query_string = urlencode(sorted(params.items()))
            
            # Generate signature
            signature = self._generate_hmac_signature(self.api_secret, query_string)
            params['signature'] = signature
            
            # Add API key header
            headers['X-MEXC-APIKEY'] = self.api_key
        
        try:
            if method == 'GET':
                response = self.session.get(url, params=params, headers=headers, timeout=10)
            elif method == 'POST':
                response = self.session.post(url, params=params, json=body, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = self.session.delete(url, params=params, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"MEXC request failed: {method} {url} - {e}")
            raise
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to MEXC format (BTCUSDT - uppercase, no separator)."""
        return symbol.replace('-', '').replace('_', '').upper()
    
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
            response = self._request('GET', '/api/v3/account', signed=True)
            
            if 'balances' not in response:
                logger.error(f"MEXC balance error: {response}")
                return {}
            
            balances = {}
            balance_list = response.get('balances', [])
            
            for item in balance_list:
                curr = item.get('asset', '').upper()
                available = float(item.get('free', 0))
                
                if currency and curr != currency.upper():
                    continue
                
                if available > 0:
                    balances[curr] = available
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get MEXC balance: {e}")
            return {}
    
    def place_order(self, symbol: str, side: str, order_type: str,
                   quantity: float, price: Optional[float] = None,
                   time_in_force: str = "GTC") -> Dict[str, Any]:
        """
        Place order on MEXC.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT" or "BTCUSDT")
            side: "BUY" or "SELL"
            order_type: "MARKET" or "LIMIT"
            quantity: Order quantity
            price: Limit price (required for limit orders)
            time_in_force: GTC, IOC, FOK
            
        Returns:
            Order response with order ID
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            params = {
                'symbol': normalized_symbol,
                'side': side.upper(),
                'type': order_type.upper(),
                'quantity': str(quantity)
            }
            
            if order_type.lower() == 'limit':
                if price is None:
                    raise ValueError("Price required for limit orders")
                params['price'] = str(price)
                params['timeInForce'] = time_in_force
            
            response = self._request('POST', '/api/v3/order', params=params, signed=True)
            
            if 'code' in response and response['code'] != 200:
                logger.error(f"MEXC order error: {response.get('msg')}")
                raise Exception(f"Order failed: {response.get('msg')}")
            
            return {
                'order_id': str(response.get('orderId')),
                'client_order_id': response.get('clientOrderId'),
                'status': response.get('status', 'submitted').lower(),
                'symbol': normalized_symbol,
                'side': side.lower(),
                'type': order_type.lower(),
                'quantity': quantity,
                'price': price,
                'transact_time': response.get('transactTime')
            }
            
        except Exception as e:
            logger.error(f"Failed to place MEXC order: {e}")
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an open order on MEXC.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair
            
        Returns:
            Cancellation confirmation
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            params = {
                'symbol': normalized_symbol,
                'orderId': order_id
            }
            
            response = self._request('DELETE', '/api/v3/order', params=params, signed=True)
            
            if 'code' in response and response['code'] != 200:
                logger.error(f"MEXC cancel error: {response.get('msg')}")
                raise Exception(f"Cancel failed: {response.get('msg')}")
            
            return {
                'order_id': str(response.get('orderId')),
                'client_order_id': response.get('clientOrderId'),
                'status': 'cancelled',
                'symbol': normalized_symbol
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel MEXC order: {e}")
            raise
    
    def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Get order status from MEXC.
        
        Args:
            order_id: Order ID to query
            symbol: Trading pair
            
        Returns:
            Order details including status and fill information
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            params = {
                'symbol': normalized_symbol,
                'orderId': order_id
            }
            
            response = self._request('GET', '/api/v3/order', params=params, signed=True)
            
            if 'code' in response and response['code'] != 200:
                logger.error(f"MEXC order query error: {response.get('msg')}")
                return {}
            
            if not response:
                return {}
            
            return {
                'order_id': str(response.get('orderId')),
                'client_order_id': response.get('clientOrderId'),
                'symbol': response.get('symbol'),
                'side': response.get('side', '').lower(),
                'type': response.get('type', '').lower(),
                'status': response.get('status', '').lower(),
                'quantity': float(response.get('origQty', 0)),
                'price': float(response.get('price', 0)),
                'executed_qty': float(response.get('executedQty', 0)),
                'executed_value': float(response.get('cummulativeQuoteQty', 0)),
                'avg_price': (float(response.get('cummulativeQuoteQty', 0)) / 
                            float(response.get('executedQty', 1)) 
                            if float(response.get('executedQty', 0)) > 0 else 0),
                'time_in_force': response.get('timeInForce'),
                'created_time': response.get('time'),
                'updated_time': response.get('updateTime')
            }
            
        except Exception as e:
            logger.error(f"Failed to get MEXC order status: {e}")
            return {}
