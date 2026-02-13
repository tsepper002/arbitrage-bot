#!/usr/bin/env python3
"""
Base REST API client for cryptocurrency exchanges.
Provides common functionality for authenticated API requests.
"""
import hashlib
import hmac
import time
import logging
import requests
from typing import Dict, Optional, Any
from abc import ABC, abstractmethod

logger = logging.getLogger("rest_client")


class BaseRestClient(ABC):
    """
    Abstract base class for exchange REST API clients.
    Implements common patterns for HMAC signature authentication.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None,
                 api_passphrase: Optional[str] = None):
        """
        Initialize REST client with API credentials.
        
        Args:
            api_key: API key for authentication
            api_secret: API secret for signing requests
            api_passphrase: API passphrase (required for some exchanges like KuCoin)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'ArbitrageBot/1.0'
        })
    
    @abstractmethod
    def _get_base_url(self) -> str:
        """Return the base URL for the exchange API."""
        pass
    
    @abstractmethod
    def _sign_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     body: Optional[Dict] = None) -> Dict[str, str]:
        """
        Generate signature and headers for authenticated request.
        Each exchange has different signature requirements.
        
        Returns:
            Dictionary of headers to add to the request
        """
        pass
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                body: Optional[Dict] = None, signed: bool = False) -> Dict[str, Any]:
        """
        Make HTTP request to exchange API.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            body: Request body (for POST/PUT)
            signed: Whether to sign the request with API credentials
            
        Returns:
            Response JSON as dictionary
            
        Raises:
            requests.RequestException: On network or HTTP errors
        """
        url = self._get_base_url() + endpoint
        headers = {}
        
        if signed:
            if not self.api_key or not self.api_secret:
                raise ValueError("API credentials required for signed requests")
            headers.update(self._sign_request(method, endpoint, params, body))
        
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
            
        except requests.RequestException as e:
            logger.error(f"Request failed: {method} {url} - {e}")
            raise
    
    def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """
        Get account balance(s).
        
        Args:
            currency: Specific currency to query, or None for all
            
        Returns:
            Dictionary of currency -> available balance
        """
        raise NotImplementedError("Subclass must implement get_balance()")
    
    def place_order(self, symbol: str, side: str, order_type: str,
                   quantity: float, price: Optional[float] = None,
                   time_in_force: str = "GTC") -> Dict[str, Any]:
        """
        Place an order on the exchange.
        
        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            side: "buy" or "sell"
            order_type: "market" or "limit"
            quantity: Order quantity in base asset
            price: Limit price (required for limit orders)
            time_in_force: Order time in force (GTC, IOC, FOK)
            
        Returns:
            Order response with order_id and status
        """
        raise NotImplementedError("Subclass must implement place_order()")
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair
            
        Returns:
            Cancellation confirmation
        """
        raise NotImplementedError("Subclass must implement cancel_order()")
    
    def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Get status of an order.
        
        Args:
            order_id: Order ID to query
            symbol: Trading pair
            
        Returns:
            Order status including fill information
        """
        raise NotImplementedError("Subclass must implement get_order_status()")
    
    @staticmethod
    def _generate_hmac_signature(secret: str, message: str, hash_func=hashlib.sha256) -> str:
        """Generate HMAC signature."""
        return hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hash_func
        ).hexdigest()
    
    @staticmethod
    def _get_timestamp_ms() -> int:
        """Get current timestamp in milliseconds."""
        return int(time.time() * 1000)
