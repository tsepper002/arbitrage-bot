#!/usr/bin/env python3
"""
XT.COM REST API client with HMAC SHA256 authentication.
API Documentation: https://doc.xt.com/
"""
import os
import logging
import json
from typing import Dict, Optional, Any
from urllib.parse import urlencode
from .base_rest import BaseRestClient

logger = logging.getLogger(__name__)


class XTRestClient(BaseRestClient):
    """
    XT.COM REST API client.
    Implements HMAC SHA256 authentication with timestamp and params.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize XT REST client.
        
        Args:
            api_key: XT API key (defaults to XT_API_KEY env var)
            api_secret: XT API secret (defaults to XT_API_SECRET env var)
        """
        api_key = api_key or os.getenv('XT_API_KEY')
        api_secret = api_secret or os.getenv('XT_API_SECRET')
        super().__init__(api_key, api_secret)
        
    def _get_base_url(self) -> str:
        """Return XT.COM API base URL."""
        return "https://sapi.xt.com"
    
    def _sign_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     body: Optional[Dict] = None) -> Dict[str, str]:
        """
        Generate XT.COM API signature.
        
        Signature format: timestamp + "#" + method + "#" + endpoint + "#" + sorted_params
        
        Returns:
            Headers with signature and authentication
        """
        timestamp = str(self._get_timestamp_ms())
        
        # Build parameter string
        sign_params = {}
        if params:
            sign_params.update(params)
        if body:
            sign_params.update(body)
        
        # Sort parameters and create query string
        param_str = ""
        if sign_params:
            sorted_params = sorted(sign_params.items())
            param_str = urlencode(sorted_params)
        
        # Create signature message: timestamp#method#endpoint#params
        message = f"{timestamp}#{method}#{endpoint}#{param_str}"
        signature = self._generate_hmac_signature(self.api_secret, message)
        
        return {
            'validate-algorithms': 'HmacSHA256',
            'validate-appkey': self.api_key,
            'validate-recvwindow': '60000',
            'validate-timestamp': timestamp,
            'validate-signature': signature
        }
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to XT format (btc_usdt - lowercase with underscore)."""
        symbol = symbol.lower()
        if '-' in symbol:
            return symbol.replace('-', '_')
        elif '_' not in symbol and len(symbol) > 3:
            # Try to split BTCUSDT -> btc_usdt
            for common_quote in ['usdt', 'usdc', 'btc', 'eth']:
                if symbol.endswith(common_quote):
                    base = symbol[:-len(common_quote)]
                    return f"{base}_{common_quote}"
        return symbol
    
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
            params = {}
            if currency:
                params['currency'] = currency.lower()
            
            response = self._request('GET', '/v4/balances', 
                                   params=params, signed=True)
            
            if response.get('rc') != 0:
                logger.error(f"XT balance error: {response.get('mc')}")
                return {}
            
            balances = {}
            balance_list = response.get('result', {}).get('assets', [])
            
            for item in balance_list:
                curr = item.get('currency', '').upper()
                available = float(item.get('available', 0))
                
                if available > 0:
                    balances[curr] = available
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get XT balance: {e}")
            return {}
    
    def place_order(self, symbol: str, side: str, order_type: str,
                   quantity: float, price: Optional[float] = None,
                   time_in_force: str = "GTC") -> Dict[str, Any]:
        """
        Place order on XT.COM.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT" or "btc_usdt")
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
            
            body = {
                'symbol': normalized_symbol,
                'side': side.upper(),
                'type': order_type.upper(),
                'quantity': str(quantity),
                'timeInForce': time_in_force
            }
            
            if order_type.lower() == 'limit':
                if price is None:
                    raise ValueError("Price required for limit orders")
                body['price'] = str(price)
            
            response = self._request('POST', '/v4/order', body=body, signed=True)
            
            if response.get('rc') != 0:
                logger.error(f"XT order error: {response.get('mc')}")
                raise Exception(f"Order failed: {response.get('mc')}")
            
            result = response.get('result', {})
            return {
                'order_id': result.get('orderId'),
                'client_order_id': result.get('clientOrderId'),
                'status': 'submitted',
                'symbol': normalized_symbol,
                'side': side.lower(),
                'type': order_type.lower(),
                'quantity': quantity,
                'price': price
            }
            
        except Exception as e:
            logger.error(f"Failed to place XT order: {e}")
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an open order on XT.COM.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair
            
        Returns:
            Cancellation confirmation
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            body = {
                'orderId': order_id,
                'symbol': normalized_symbol
            }
            
            response = self._request('DELETE', '/v4/order', body=body, signed=True)
            
            if response.get('rc') != 0:
                logger.error(f"XT cancel error: {response.get('mc')}")
                raise Exception(f"Cancel failed: {response.get('mc')}")
            
            result = response.get('result', {})
            return {
                'order_id': result.get('orderId'),
                'status': 'cancelled',
                'symbol': normalized_symbol
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel XT order: {e}")
            raise
    
    def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Get order status from XT.COM.
        
        Args:
            order_id: Order ID to query
            symbol: Trading pair
            
        Returns:
            Order details including status and fill information
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            params = {
                'orderId': order_id,
                'symbol': normalized_symbol
            }
            
            response = self._request('GET', '/v4/order', params=params, signed=True)
            
            if response.get('rc') != 0:
                logger.error(f"XT order query error: {response.get('mc')}")
                return {}
            
            order = response.get('result', {})
            if not order:
                return {}
            
            return {
                'order_id': order.get('orderId'),
                'client_order_id': order.get('clientOrderId'),
                'symbol': order.get('symbol'),
                'side': order.get('side', '').lower(),
                'type': order.get('type', '').lower(),
                'status': order.get('state', '').lower(),
                'quantity': float(order.get('origQty', 0)),
                'price': float(order.get('price', 0)),
                'executed_qty': float(order.get('executedQty', 0)),
                'executed_value': float(order.get('executedAmount', 0)),
                'avg_price': float(order.get('avgPrice', 0)),
                'created_time': order.get('createTime'),
                'updated_time': order.get('updateTime')
            }
            
        except Exception as e:
            logger.error(f"Failed to get XT order status: {e}")
            return {}
