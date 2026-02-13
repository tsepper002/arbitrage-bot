#!/usr/bin/env python3
"""
Bybit REST API client with HMAC SHA256 authentication.
API Documentation: https://bybit-exchange.github.io/docs/v5/intro
"""
import os
import logging
import json
from typing import Dict, Optional, Any
from urllib.parse import urlencode
from .base_rest import BaseRestClient

logger = logging.getLogger(__name__)


class BybitRestClient(BaseRestClient):
    """
    Bybit REST API client.
    Implements V5 unified trading API with HMAC SHA256 authentication.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Bybit REST client.
        
        Args:
            api_key: Bybit API key (defaults to BYBIT_API_KEY env var)
            api_secret: Bybit API secret (defaults to BYBIT_API_SECRET env var)
        """
        api_key = api_key or os.getenv('BYBIT_API_KEY')
        api_secret = api_secret or os.getenv('BYBIT_API_SECRET')
        super().__init__(api_key, api_secret)
        
    def _get_base_url(self) -> str:
        """Return Bybit V5 API base URL."""
        return "https://api.bybit.com"
    
    def _sign_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     body: Optional[Dict] = None) -> Dict[str, str]:
        """
        Generate Bybit V5 API signature.
        
        Signature format: timestamp + api_key + recv_window + query_string (+ body)
        
        Returns:
            Headers with signature and authentication
        """
        timestamp = str(self._get_timestamp_ms())
        recv_window = "5000"
        
        # Build param string
        param_str = ""
        if method == "GET" and params:
            param_str = urlencode(sorted(params.items()))
        elif method in ["POST", "DELETE"] and body:
            param_str = json.dumps(body, separators=(',', ':'))
        
        # Create signature message
        message = f"{timestamp}{self.api_key}{recv_window}{param_str}"
        signature = self._generate_hmac_signature(self.api_secret, message)
        
        return {
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-SIGN': signature,
            'X-BAPI-TIMESTAMP': timestamp,
            'X-BAPI-RECV-WINDOW': recv_window,
            'X-BAPI-SIGN-TYPE': '2'
        }
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Bybit format (BTCUSDT - uppercase, no separator)."""
        return symbol.replace('-', '').replace('_', '').upper()
    
    def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """
        Get account balance from unified trading account.
        
        Args:
            currency: Specific coin to query (e.g., 'BTC', 'USDT')
            
        Returns:
            Dictionary of currency -> available balance
            
        Example:
            {'BTC': 0.5, 'USDT': 10000.0}
        """
        try:
            params = {'accountType': 'UNIFIED'}
            if currency:
                params['coin'] = currency.upper()
            
            response = self._request('GET', '/v5/account/wallet-balance', 
                                   params=params, signed=True)
            
            if response.get('retCode') != 0:
                logger.error(f"Bybit balance error: {response.get('retMsg')}")
                return {}
            
            balances = {}
            result_list = response.get('result', {}).get('list', [])
            if result_list:
                coins = result_list[0].get('coin', [])
                for coin in coins:
                    coin_name = coin.get('coin')
                    available = float(coin.get('availableToWithdraw', 0))
                    if available > 0:
                        balances[coin_name] = available
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get Bybit balance: {e}")
            return {}
    
    def place_order(self, symbol: str, side: str, order_type: str,
                   quantity: float, price: Optional[float] = None,
                   time_in_force: str = "GTC") -> Dict[str, Any]:
        """
        Place order on Bybit unified trading account.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT" or "BTCUSDT")
            side: "Buy" or "Sell"
            order_type: "Market" or "Limit"
            quantity: Order quantity
            price: Limit price (required for limit orders)
            time_in_force: GTC, IOC, FOK, PostOnly
            
        Returns:
            Order response with orderId, orderLinkId, and status
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            body = {
                'category': 'spot',
                'symbol': normalized_symbol,
                'side': side.capitalize(),
                'orderType': order_type.capitalize(),
                'qty': str(quantity),
                'timeInForce': time_in_force
            }
            
            if order_type.lower() == 'limit':
                if price is None:
                    raise ValueError("Price required for limit orders")
                body['price'] = str(price)
            
            response = self._request('POST', '/v5/order/create', body=body, signed=True)
            
            if response.get('retCode') != 0:
                logger.error(f"Bybit order error: {response.get('retMsg')}")
                raise Exception(f"Order failed: {response.get('retMsg')}")
            
            result = response.get('result', {})
            return {
                'order_id': result.get('orderId'),
                'order_link_id': result.get('orderLinkId'),
                'status': 'submitted',
                'symbol': normalized_symbol,
                'side': side.lower(),
                'type': order_type.lower(),
                'quantity': quantity,
                'price': price
            }
            
        except Exception as e:
            logger.error(f"Failed to place Bybit order: {e}")
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an open order on Bybit.
        
        Args:
            order_id: Order ID or orderLinkId
            symbol: Trading pair
            
        Returns:
            Cancellation confirmation
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            body = {
                'category': 'spot',
                'symbol': normalized_symbol,
                'orderId': order_id
            }
            
            response = self._request('POST', '/v5/order/cancel', body=body, signed=True)
            
            if response.get('retCode') != 0:
                logger.error(f"Bybit cancel error: {response.get('retMsg')}")
                raise Exception(f"Cancel failed: {response.get('retMsg')}")
            
            result = response.get('result', {})
            return {
                'order_id': result.get('orderId'),
                'status': 'cancelled',
                'symbol': normalized_symbol
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel Bybit order: {e}")
            raise
    
    def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Get order status from Bybit.
        
        Args:
            order_id: Order ID to query
            symbol: Trading pair
            
        Returns:
            Order details including status and fill information
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            params = {
                'category': 'spot',
                'orderId': order_id
            }
            
            response = self._request('GET', '/v5/order/realtime', 
                                   params=params, signed=True)
            
            if response.get('retCode') != 0:
                logger.error(f"Bybit order query error: {response.get('retMsg')}")
                return {}
            
            result_list = response.get('result', {}).get('list', [])
            if not result_list:
                return {}
            
            order = result_list[0]
            return {
                'order_id': order.get('orderId'),
                'order_link_id': order.get('orderLinkId'),
                'symbol': order.get('symbol'),
                'side': order.get('side', '').lower(),
                'type': order.get('orderType', '').lower(),
                'status': order.get('orderStatus', '').lower(),
                'quantity': float(order.get('qty', 0)),
                'price': float(order.get('price', 0)),
                'executed_qty': float(order.get('cumExecQty', 0)),
                'executed_value': float(order.get('cumExecValue', 0)),
                'avg_price': float(order.get('avgPrice', 0)),
                'created_time': order.get('createdTime'),
                'updated_time': order.get('updatedTime')
            }
            
        except Exception as e:
            logger.error(f"Failed to get Bybit order status: {e}")
            return {}
