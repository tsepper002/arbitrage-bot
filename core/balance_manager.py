#!/usr/bin/env python3
"""
Balance Manager - Track and manage balances across all exchanges.
Handles balance queries, caching, and pre-trade verification.
"""
import asyncio
import logging
import time
from typing import Dict, Optional, List
from dataclasses import dataclass
import os

logger = logging.getLogger("balance_manager")


@dataclass
class Balance:
    """Balance information for a currency."""
    total: float
    available: float
    locked: float
    last_updated: float


class BalanceManager:
    """
    Manages account balances across multiple exchanges.
    Provides real-time balance tracking and pre-trade verification.
    """
    
    def __init__(self, rest_clients: Optional[Dict[str, any]] = None):
        """
        Initialize balance manager.
        
        Args:
            rest_clients: Dictionary of exchange_name -> REST client instance
        """
        self.rest_clients = rest_clients or {}
        # balances[exchange][currency] = Balance
        self.balances: Dict[str, Dict[str, Balance]] = {}
        self.last_fetch_time: Dict[str, float] = {}
        self.cache_ttl = 30.0  # Cache balance for 30 seconds
        self._lock = asyncio.Lock()
        
        logger.info("BalanceManager initialized")
    
    def add_exchange(self, exchange_name: str, rest_client):
        """Add a REST client for an exchange."""
        self.rest_clients[exchange_name] = rest_client
        self.balances[exchange_name] = {}
        logger.info(f"Added exchange to balance manager: {exchange_name}")
    
    async def fetch_balances(self, exchange: Optional[str] = None, force: bool = False) -> Dict[str, Dict[str, Balance]]:
        """
        Fetch current balances from exchanges.
        
        Args:
            exchange: Specific exchange to fetch, or None for all
            force: Force refresh even if cache is valid
            
        Returns:
            Dictionary of exchange -> currency -> Balance
        """
        async with self._lock:
            exchanges_to_fetch = [exchange] if exchange else list(self.rest_clients.keys())
            
            for ex in exchanges_to_fetch:
                # Check cache
                last_fetch = self.last_fetch_time.get(ex, 0)
                if not force and (time.time() - last_fetch) < self.cache_ttl:
                    logger.debug(f"Using cached balances for {ex}")
                    continue
                
                client = self.rest_clients.get(ex)
                if not client:
                    logger.warning(f"No REST client for {ex}")
                    continue
                
                try:
                    # Fetch balances (this is synchronous, run in executor)
                    loop = asyncio.get_event_loop()
                    balance_data = await loop.run_in_executor(None, client.get_balance)
                    
                    # Update balances
                    if exchange not in self.balances:
                        self.balances[ex] = {}
                    
                    current_time = time.time()
                    for currency, balance_info in balance_data.items():
                        if isinstance(balance_info, dict):
                            total = float(balance_info.get('total', 0))
                            available = float(balance_info.get('available', balance_info.get('free', total)))
                            locked = float(balance_info.get('locked', 0))
                        else:
                            # Simple float balance
                            total = available = float(balance_info)
                            locked = 0.0
                        
                        self.balances[ex][currency] = Balance(
                            total=total,
                            available=available,
                            locked=locked,
                            last_updated=current_time
                        )
                    
                    self.last_fetch_time[ex] = current_time
                    logger.info(f"Fetched balances for {ex}: {len(balance_data)} currencies")
                    
                except Exception as e:
                    logger.error(f"Failed to fetch balances for {ex}: {e}")
            
            return self.balances
    
    def get_balance(self, exchange: str, currency: str) -> Optional[Balance]:
        """
        Get balance for a specific currency on an exchange.
        
        Args:
            exchange: Exchange name
            currency: Currency symbol (e.g., "BTC", "USDT")
            
        Returns:
            Balance object or None if not available
        """
        return self.balances.get(exchange, {}).get(currency)
    
    def get_available_balance(self, exchange: str, currency: str) -> float:
        """
        Get available balance for trading.
        
        Args:
            exchange: Exchange name
            currency: Currency symbol
            
        Returns:
            Available balance (0.0 if not found)
        """
        balance = self.get_balance(exchange, currency)
        return balance.available if balance else 0.0
    
    def verify_balances_for_trade(self, buy_exchange: str, sell_exchange: str,
                                  symbol: str, quantity: float, buy_price: float,
                                  sell_price: float) -> Tuple[bool, Optional[str]]:
        """
        Verify sufficient balances exist for an arbitrage trade.
        
        Args:
            buy_exchange: Exchange to buy from
            sell_exchange: Exchange to sell on
            symbol: Trading pair (e.g., "BTC-USDT")
            quantity: Amount to trade (in base currency)
            buy_price: Price to buy at
            sell_price: Price to sell at
            
        Returns:
            (success, error_message) tuple
        """
        # Parse symbol to get base and quote currencies
        if "-" in symbol:
            base, quote = symbol.split("-")
        else:
            # Assume USDT pair if no separator
            base = symbol.replace("USDT", "")
            quote = "USDT"
        
        # Check buy exchange has enough quote currency (USDT)
        required_quote = quantity * buy_price * 1.01  # Add 1% buffer for fees
        buy_balance = self.get_available_balance(buy_exchange, quote)
        
        if buy_balance < required_quote:
            return False, f"Insufficient {quote} on {buy_exchange}: have {buy_balance:.2f}, need {required_quote:.2f}"
        
        # Check sell exchange has enough base currency (BTC, ETH, etc.)
        sell_balance = self.get_available_balance(sell_exchange, base)
        
        if sell_balance < quantity:
            return False, f"Insufficient {base} on {sell_exchange}: have {sell_balance:.6f}, need {quantity:.6f}"
        
        return True, None
    
    def get_total_balance_usdt(self, prices: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate total balance across all exchanges in USDT equivalent.
        
        Args:
            prices: Dictionary of currency -> USDT price (for conversion)
            
        Returns:
            Total balance in USDT
        """
        total = 0.0
        prices = prices or {}
        
        for exchange, currencies in self.balances.items():
            for currency, balance in currencies.items():
                if currency == "USDT" or currency == "USD":
                    total += balance.available
                elif currency in prices:
                    total += balance.available * prices[currency]
                # Skip currencies without price data
        
        return total
    
    def get_exchange_balances_usdt(self, exchange: str, prices: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate total balance for one exchange in USDT equivalent.
        
        Args:
            exchange: Exchange name
            prices: Dictionary of currency -> USDT price
            
        Returns:
            Total balance in USDT for this exchange
        """
        total = 0.0
        prices = prices or {}
        currencies = self.balances.get(exchange, {})
        
        for currency, balance in currencies.items():
            if currency == "USDT" or currency == "USD":
                total += balance.available
            elif currency in prices:
                total += balance.available * prices[currency]
        
        return total
    
    def get_summary(self) -> Dict[str, any]:
        """Get summary of all balances."""
        summary = {
            'exchanges': len(self.rest_clients),
            'balances': {}
        }
        
        for exchange, currencies in self.balances.items():
            summary['balances'][exchange] = {
                currency: {
                    'total': bal.total,
                    'available': bal.available,
                    'locked': bal.locked
                }
                for currency, bal in currencies.items()
                if bal.total > 0  # Only show non-zero balances
            }
        
        return summary
    
    def print_summary(self):
        """Print balance summary to console."""
        print("\n" + "="*60)
        print("  Balance Manager Summary")
        print("="*60)
        
        for exchange, currencies in self.balances.items():
            print(f"\n{exchange}:")
            for currency, balance in currencies.items():
                if balance.total > 0:
                    print(f"  {currency:8s}: {balance.available:12.6f} available ({balance.total:12.6f} total, {balance.locked:12.6f} locked)")
        
        print("="*60 + "\n")
