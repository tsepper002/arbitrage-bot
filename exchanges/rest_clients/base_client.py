#!/usr/bin/env python3
"""
Base REST API client for exchange integrations.
Provides common interface for authenticated REST operations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger("rest_client")


class BaseRESTClient(ABC):
    """
    Abstract base class for exchange REST API clients.
    All exchanges must implement these methods.
    """
    
    def __init__(self, api_key: str, api_secret: str, exchange_name: str):
        """
        Initialize REST client.
        
        Args:
            api_key: API key from exchange
            api_secret: API secret from exchange
            exchange_name: Name of the exchange for logging
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.exchange_name = exchange_name
        logger.info(f"{exchange_name} REST client initialized")
    
    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,  # 'buy' or 'sell'
        order_type: str,  # 'market' or 'limit'
        quantity: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """
        Place an order on the exchange.
        
        Args:
            symbol: Trading pair (e.g., 'BTC-USDT')
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            quantity: Amount to trade (in base currency)
            price: Limit price (required for limit orders)
            time_in_force: Time in force (GTC, IOC, FOK, etc.)
            
        Returns:
            Dict with order details including order_id, status, filled_quantity, etc.
            
        Raises:
            Exception on API errors
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel an open order.
        
        Args:
            symbol: Trading pair
            order_id: Exchange-specific order ID
            
        Returns:
            Dict with cancellation confirmation
            
        Raises:
            Exception on API errors
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Get status of an order.
        
        Args:
            symbol: Trading pair
            order_id: Exchange-specific order ID
            
        Returns:
            Dict with order status, filled_quantity, average_price, etc.
            
        Raises:
            Exception on API errors
        """
        pass
    
    @abstractmethod
    async def get_balance(self, currency: Optional[str] = None) -> Dict[str, float]:
        """
        Get account balances.
        
        Args:
            currency: Specific currency to query (None for all)
            
        Returns:
            Dict mapping currency -> available balance
            Example: {'USDT': 1000.0, 'BTC': 0.5}
            
        Raises:
            Exception on API errors
        """
        pass
    
    @abstractmethod
    async def get_trading_pairs(self) -> List[Dict[str, Any]]:
        """
        Get all available trading pairs and their info.
        
        Returns:
            List of dicts with pair info (symbol, base, quote, min_qty, etc.)
            
        Raises:
            Exception on API errors
        """
        pass
    
    @abstractmethod
    async def withdraw(
        self,
        currency: str,
        amount: float,
        address: str,
        network: Optional[str] = None,
        memo: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Withdraw funds to external address.
        
        Args:
            currency: Currency to withdraw
            amount: Amount to withdraw
            address: Destination address
            network: Network/chain (e.g., 'TRC20', 'ERC20', 'ARB')
            memo: Optional memo/tag
            
        Returns:
            Dict with withdrawal ID and status
            
        Raises:
            Exception on API errors
        """
        pass
    
    @abstractmethod
    async def get_deposit_address(self, currency: str, network: Optional[str] = None) -> Dict[str, str]:
        """
        Get deposit address for a currency.
        
        Args:
            currency: Currency symbol
            network: Network/chain
            
        Returns:
            Dict with 'address' and optionally 'memo'
            
        Raises:
            Exception on API errors
        """
        pass
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format to exchange-specific format.
        Default implementation, override if needed.
        
        Args:
            symbol: Standard format like 'BTC-USDT'
            
        Returns:
            Exchange-specific format
        """
        return symbol
    
    def denormalize_symbol(self, symbol: str) -> str:
        """
        Convert exchange-specific symbol to standard format.
        Default implementation, override if needed.
        
        Args:
            symbol: Exchange-specific format
            
        Returns:
            Standard format like 'BTC-USDT'
        """
        return symbol
