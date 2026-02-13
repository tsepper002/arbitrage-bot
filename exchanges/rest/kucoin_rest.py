#!/usr/bin/env python3
"""
KuCoin REST API client with HMAC SHA256 authentication.
API Documentation: https://docs.kucoin.com/
"""
import os
import logging
import json
import base64
from typing import Dict, Optional, Any
from .base_rest import BaseRestClient

logger = logging.getLogger(__name__)


class KuCoinRestClient(BaseRestClient):
    """
    KuCoin REST API client.
    Implements HMAC SHA256 authentication with passphrase requirement.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None,
                 api_passphrase: Optional[str] = None):
        """
        Initialize KuCoin REST client.
        
        Args:
            api_key: KuCoin API key (defaults to KUCOIN_API_KEY env var)
            api_secret: KuCoin API secret (defaults to KUCOIN_API_SECRET env var)
            api_passphrase: KuCoin API passphrase (defaults to KUCOIN_API_PASSPHRASE env var)
        """
        api_key = api_key or os.getenv('KUCOIN_API_KEY')
        api_secret = api_secret or os.getenv('KUCOIN_API_SECRET')
        api_passphrase = api_passphrase or os.getenv('KUCOIN_API_PASSPHRASE')
        super().__init__(api_key, api_secret, api_passphrase)
        
    def _get_base_url(self) -> str:
        """Return KuCoin API base URL."""
        return "https://api.kucoin.com"
    
    def _sign_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     body: Optional[Dict] = None) -> Dict[str, str]:
        """
        Generate KuCoin API signature.
        
        Signature format: timestamp + method + endpoint + body
        Passphrase is also signed: HMAC(passphrase, secret)
        
        Returns:
            Headers with signature and authentication
        """
        timestamp = str(self._get_timestamp_ms())
        
        # Build the request body string
        body_str = ""
        if body:
            body_str = json.dumps(body, separators=(',', ':'))
        
        # Create signature message: timestamp + method + endpoint + body
        message = f"{timestamp}{method}{endpoint}{body_str}"
        signature = base64.b64encode(
            self._generate_hmac_signature(self.api_secret, message).encode()
        ).decode()
        
        # Sign the passphrase
        passphrase_signature = base64.b64encode(
            self._generate_hmac_signature(self.api_secret, self.api_passphrase).encode()
        ).decode()
        
        return {
            'KC-API-KEY': self.api_key,
            'KC-API-SIGN': signature,
            'KC-API-TIMESTAMP': timestamp,
            'KC-API-PASSPHRASE': passphrase_signature,
            'KC-API-KEY-VERSION': '2'
        }
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to KuCoin format (BTC-USDT)."""
        if '_' in symbol:
            return symbol.replace('_', '-')
        elif '-' not in symbol and len(symbol) > 3:
            # Try to split BTCUSDT -> BTC-USDT
            for common_quote in ['USDT', 'USDC', 'BTC', 'ETH']:
                if symbol.endswith(common_quote):
                    base = symbol[:-len(common_quote)]
                    return f"{base}-{common_quote}"
        return symbol
    
    def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """
        Get account balance from trading account.
        
        Args:
            currency: Specific currency to query (e.g., 'BTC', 'USDT')
            
        Returns:
            Dictionary of currency -> available balance
            
        Example:
            {'BTC': 0.5, 'USDT': 10000.0}
        """
        try:
            params = {'type': 'trade'}
            if currency:
                params['currency'] = currency.upper()
            
            response = self._request('GET', '/api/v1/accounts', 
                                   params=params, signed=True)
            
            if response.get('code') != '200000':
                logger.error(f"KuCoin balance error: {response.get('msg')}")
                return {}
            
            balances = {}
            accounts = response.get('data', [])
            for account in accounts:
                currency_name = account.get('currency')
                available = float(account.get('available', 0))
                if available > 0:
                    balances[currency_name] = available
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get KuCoin balance: {e}")
            return {}
    
    def place_order(self, symbol: str, side: str, order_type: str,
                   quantity: float, price: Optional[float] = None,
                   time_in_force: str = "GTC") -> Dict[str, Any]:
        """
        Place order on KuCoin.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            side: "buy" or "sell"
            order_type: "market" or "limit"
            quantity: Order size (in base currency for market sell, quote for market buy)
            price: Limit price (required for limit orders)
            time_in_force: GTC, GTT, IOC, FOK
            
        Returns:
            Order response with orderId
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            body = {
                'clientOid': str(self._get_timestamp_ms()),
                'side': side.lower(),
                'symbol': normalized_symbol,
                'type': order_type.lower()
            }
            
            if order_type.lower() == 'limit':
                if price is None:
                    raise ValueError("Price required for limit orders")
                body['price'] = str(price)
                body['size'] = str(quantity)
                body['timeInForce'] = time_in_force
            else:
                # Market order: for buy use 'funds', for sell use 'size'
                if side.lower() == 'buy':
                    body['funds'] = str(quantity)  # Quote currency amount
                else:
                    body['size'] = str(quantity)   # Base currency amount
            
            response = self._request('POST', '/api/v1/orders', body=body, signed=True)
            
            if response.get('code') != '200000':
                logger.error(f"KuCoin order error: {response.get('msg')}")
                raise Exception(f"Order failed: {response.get('msg')}")
            
            result = response.get('data', {})
            return {
                'order_id': result.get('orderId'),
                'status': 'submitted',
                'symbol': normalized_symbol,
                'side': side.lower(),
                'type': order_type.lower(),
                'quantity': quantity,
                'price': price
            }
            
        except Exception as e:
            logger.error(f"Failed to place KuCoin order: {e}")
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an open order on KuCoin.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair (not used in API call but kept for consistency)
            
        Returns:
            Cancellation confirmation
        """
        try:
            response = self._request('DELETE', f'/api/v1/orders/{order_id}', signed=True)
            
            if response.get('code') != '200000':
                logger.error(f"KuCoin cancel error: {response.get('msg')}")
                raise Exception(f"Cancel failed: {response.get('msg')}")
            
            return {
                'order_id': order_id,
                'status': 'cancelled',
                'cancel_ids': response.get('data', {}).get('cancelledOrderIds', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel KuCoin order: {e}")
            raise
    
    def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Get order status from KuCoin.
        
        Args:
            order_id: Order ID to query
            symbol: Trading pair (not used in API call but kept for consistency)
            
        Returns:
            Order details including status and fill information
        """
        try:
            response = self._request('GET', f'/api/v1/orders/{order_id}', signed=True)
            
            if response.get('code') != '200000':
                logger.error(f"KuCoin order query error: {response.get('msg')}")
                return {}
            
            order = response.get('data', {})
            if not order:
                return {}
            
            return {
                'order_id': order.get('id'),
                'symbol': order.get('symbol'),
                'side': order.get('side'),
                'type': order.get('type'),
                'status': order.get('isActive') and 'active' or 'done',
                'quantity': float(order.get('size', 0)),
                'price': float(order.get('price', 0)),
                'executed_qty': float(order.get('dealSize', 0)),
                'executed_value': float(order.get('dealFunds', 0)),
                'fee': float(order.get('fee', 0)),
                'fee_currency': order.get('feeCurrency'),
                'created_time': order.get('createdAt'),
                'stop_price': order.get('stopPrice')
            }
            
        except Exception as e:
            logger.error(f"Failed to get KuCoin order status: {e}")
            return {}
