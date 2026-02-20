#!/usr/bin/env python3
"""
Smart Capital Allocator - Intelligent capital distribution for minimal balances.

Enables trading with as little as $8 per exchange while maximizing efficiency.
Dynamically scales trade sizes based on available capital across exchanges.
"""
import logging
from typing import Dict, Tuple, Optional, List
import settings

logger = logging.getLogger("smart_capital_allocator")


class SmartCapitalAllocator:
    """
    Intelligently allocates capital for arbitrage trades based on:
    - Available balance on each exchange
    - Risk limits and safety factors
    - Minimum viable trade sizes
    - Exchange reliability and fees
    
    Key Features:
    - Works with minimal balances ($8+ per exchange)
    - Proportional allocation based on capital
    - Protects small balances with reserves
    - Scales trade sizes dynamically
    """
    
    def __init__(self, balance_manager=None):
        """
        Initialize smart capital allocator.
        
        Args:
            balance_manager: BalanceManager instance for accessing balances
        """
        self.balance_manager = balance_manager
        
        # Configuration from settings
        self.min_balance = settings.MIN_BALANCE_PER_EXCHANGE
        self.min_trade_size = settings.MIN_TRADE_SIZE_USDT
        self.balance_reserve = settings.BALANCE_RESERVE_USDT
        self.max_usage_pct = settings.MAX_BALANCE_USAGE_PCT / 100.0
        self.max_exposure = settings.MAX_EXPOSURE_USDT
        
        logger.info(
            f"SmartCapitalAllocator initialized: "
            f"min_balance=${self.min_balance}, "
            f"min_trade=${self.min_trade_size}, "
            f"reserve=${self.balance_reserve}, "
            f"max_usage={self.max_usage_pct*100}%"
        )
    
    def get_available_capital(self, exchange: str, currency: str = 'USDT') -> float:
        """
        Get available capital for trading on an exchange.
        
        Args:
            exchange: Exchange name
            currency: Currency symbol (default: USDT)
            
        Returns:
            Available capital in USDT, after accounting for reserves
        """
        if not self.balance_manager:
            # No balance manager - use max exposure in dry-run
            if settings.DRY_RUN:
                return self.max_exposure
            return 0.0
        
        if exchange not in self.balance_manager.balances:
            # No balance data
            if settings.DRY_RUN:
                return self.max_exposure
            return 0.0
        
        balance = self.balance_manager.balances[exchange].get(currency, 0)
        
        # Subtract reserve to protect minimum balance
        available = max(0, balance - self.balance_reserve)
        
        return available
    
    def calculate_max_trade_size(
        self,
        exchange: str,
        currency: str = 'USDT'
    ) -> float:
        """
        Calculate maximum trade size for an exchange.
        
        Considers:
        - Available balance
        - Reserve requirements
        - Maximum usage percentage
        - Global exposure limits
        
        Args:
            exchange: Exchange name
            currency: Currency symbol
            
        Returns:
            Maximum trade size in USDT
        """
        available = self.get_available_capital(exchange, currency)
        
        if available < self.min_trade_size:
            logger.debug(
                f"{exchange}: Insufficient capital ${available:.2f} "
                f"< min ${self.min_trade_size}"
            )
            return 0.0
        
        # Apply maximum usage percentage
        max_from_balance = available * self.max_usage_pct
        
        # Cap at global exposure limit
        max_trade = min(max_from_balance, self.max_exposure)
        
        # Ensure meets minimum trade size
        if max_trade < self.min_trade_size:
            return 0.0
        
        return max_trade
    
    def allocate_for_arbitrage(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        desired_quantity: float = None,
        currency: str = 'USDT'
    ) -> Tuple[float, Dict[str, str]]:
        """
        Calculate optimal trade quantity for cross-exchange arbitrage.
        
        Uses the SMALLER of the two exchange limits to ensure both sides
        can execute. This prevents partial fills and stuck positions.
        
        Args:
            buy_exchange: Exchange to buy on
            sell_exchange: Exchange to sell on
            symbol: Trading symbol
            desired_quantity: Desired trade quantity (optional)
            currency: Quote currency
            
        Returns:
            (trade_quantity_usdt, allocation_info) tuple where:
            - trade_quantity_usdt: Allocated trade size in USDT
            - allocation_info: Dict with allocation details and reasons
        """
        # Get max trade sizes for both exchanges
        buy_max = self.calculate_max_trade_size(buy_exchange, currency)
        sell_max = self.calculate_max_trade_size(sell_exchange, currency)
        
        # Use the smaller limit (bottleneck)
        allocated_size = min(buy_max, sell_max)
        
        # Check if desired quantity specified
        if desired_quantity is not None:
            allocated_size = min(allocated_size, desired_quantity)
        
        # Ensure meets minimum
        if allocated_size < self.min_trade_size:
            allocated_size = 0.0
            reason = f"Below minimum trade size ${self.min_trade_size}"
        else:
            reason = "Optimal allocation"
        
        # Determine bottleneck
        bottleneck = None
        if buy_max < sell_max:
            bottleneck = buy_exchange
        elif sell_max < buy_max:
            bottleneck = sell_exchange
        
        allocation_info = {
            'buy_exchange': buy_exchange,
            'sell_exchange': sell_exchange,
            'buy_max': f"${buy_max:.2f}",
            'sell_max': f"${sell_max:.2f}",
            'allocated': f"${allocated_size:.2f}",
            'bottleneck': bottleneck,
            'reason': reason
        }
        
        logger.debug(
            f"Arbitrage allocation: {buy_exchange}→{sell_exchange} "
            f"max(${buy_max:.2f}, ${sell_max:.2f}) = ${allocated_size:.2f}"
        )
        
        return allocated_size, allocation_info
    
    def get_balance_distribution(self, currency: str = 'USDT') -> Dict[str, float]:
        """
        Get balance distribution across all exchanges.
        
        Args:
            currency: Currency to check
            
        Returns:
            Dict of {exchange: balance} for all exchanges with balances
        """
        if not self.balance_manager:
            return {}
        
        distribution = {}
        for exchange, balances in self.balance_manager.balances.items():
            balance = balances.get(currency, 0)
            if balance >= self.min_balance:
                distribution[exchange] = balance
        
        return distribution
    
    def get_allocation_strategy_info(self) -> Dict:
        """
        Get information about current allocation strategy and settings.
        
        Returns:
            Dict with strategy configuration
        """
        total_capital = 0.0
        eligible_exchanges = []
        
        if self.balance_manager:
            for exchange, balances in self.balance_manager.balances.items():
                usdt = balances.get('USDT', 0)
                if usdt >= self.min_balance:
                    total_capital += usdt
                    eligible_exchanges.append(exchange)
        
        return {
            'total_capital_usdt': total_capital,
            'eligible_exchanges': eligible_exchanges,
            'min_balance_per_exchange': self.min_balance,
            'min_trade_size': self.min_trade_size,
            'balance_reserve': self.balance_reserve,
            'max_balance_usage_pct': self.max_usage_pct * 100,
            'max_exposure_per_trade': self.max_exposure,
            'strategy': 'proportional_with_bottleneck_matching'
        }
    
    def print_allocation_summary(self):
        """Print human-readable allocation summary."""
        info = self.get_allocation_strategy_info()
        
        logger.info("=" * 60)
        logger.info("SMART CAPITAL ALLOCATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Capital: ${info['total_capital_usdt']:.2f}")
        logger.info(f"Eligible Exchanges: {len(info['eligible_exchanges'])}")
        if info['eligible_exchanges']:
            logger.info(f"  {', '.join(info['eligible_exchanges'])}")
        logger.info(f"Min Balance/Exchange: ${info['min_balance_per_exchange']:.2f}")
        logger.info(f"Min Trade Size: ${info['min_trade_size']:.2f}")
        logger.info(f"Balance Reserve: ${info['balance_reserve']:.2f}")
        logger.info(f"Max Balance Usage: {info['max_balance_usage_pct']:.1f}%")
        logger.info(f"Max Exposure/Trade: ${info['max_exposure_per_trade']:.2f}")
        logger.info(f"Strategy: {info['strategy']}")
        logger.info("=" * 60)


def get_smart_allocator(balance_manager=None):
    """
    Factory function to create SmartCapitalAllocator instance.
    
    Args:
        balance_manager: BalanceManager instance
        
    Returns:
        SmartCapitalAllocator instance
    """
    return SmartCapitalAllocator(balance_manager)
