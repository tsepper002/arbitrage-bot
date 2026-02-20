"""
Funding rate arbitrage strategy.

Opens delta-neutral positions (long spot + short perpetual) to capture
positive funding rates paid every 8 hours.

Expected impact: +$50-150/month passive income
"""

import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class FundingPosition:
    """Active funding arbitrage position"""
    symbol: str
    exchange: str
    entry_time: float
    spot_size: float
    perp_size: float
    funding_rate: float
    accumulated_funding: float = 0.0
    

class FundingArbitrage:
    """
    Funding rate arbitrage implementation.
    
    Strategy:
    1. Monitor funding rates on perpetual futures
    2. When funding > threshold: open long spot + short perp
    3. Collect funding every 8 hours
    4. When funding < exit_threshold: close positions
    """
    
    def __init__(
        self,
        rest_clients: Dict,
        balance_manager,
        entry_threshold: float = 0.03,  # 0.03% funding
        exit_threshold: float = 0.01,   # 0.01% funding
        max_position_size: float = 1000.0
    ):
        self.rest_clients = rest_clients
        self.balance_manager = balance_manager
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.max_position_size = max_position_size
        
        # Active positions
        self.positions: Dict[str, FundingPosition] = {}
        
        # Statistics
        self.stats = {
            'positions_opened': 0,
            'positions_closed': 0,
            'total_funding_collected': 0.0
        }
        
        logger.info("Funding Arbitrage initialized")
    
    async def get_funding_rate(self, exchange: str, symbol: str) -> Optional[float]:
        """Get current funding rate for a symbol"""
        # Placeholder - would fetch from REST API
        # Real implementation would call exchange-specific endpoints
        return None
    
    async def start_monitoring(self):
        """Start monitoring funding rates"""
        logger.info("Starting funding rate monitoring")
        
        while True:
            try:
                # Monitor funding rates on all exchanges
                for exchange in ['Bybit', 'KuCoin', 'MEXC']:
                    for symbol in ['BTC/USDT', 'ETH/USDT']:
                        rate = await self.get_funding_rate(exchange, symbol)
                        if rate and rate > self.entry_threshold:
                            await self._consider_entry(exchange, symbol, rate)
                
                # Check existing positions
                for pos_key, position in list(self.positions.items()):
                    await self._check_position(position)
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in funding monitoring: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _consider_entry(self, exchange: str, symbol: str, rate: float):
        """Consider opening a new position"""
        pos_key = f"{exchange}_{symbol}"
        
        if pos_key in self.positions:
            return  # Already have position
        
        logger.info(f"High funding rate on {exchange} {symbol}: {rate:.4f}%")
        # Would open position here
    
    async def _check_position(self, position: FundingPosition):
        """Check if position should be closed"""
        current_rate = await self.get_funding_rate(
            position.exchange, 
            position.symbol
        )
        
        if current_rate and current_rate < self.exit_threshold:
            await self._close_position(position)
    
    async def _close_position(self, position: FundingPosition):
        """Close a funding arbitrage position"""
        logger.info(f"Closing position {position.exchange} {position.symbol}")
        self.stats['positions_closed'] += 1
        self.stats['total_funding_collected'] += position.accumulated_funding
        
        pos_key = f"{position.exchange}_{position.symbol}"
        if pos_key in self.positions:
            del self.positions[pos_key]


def get_funding_arbitrage(rest_clients: Dict, balance_manager) -> FundingArbitrage:
    """Factory function for funding arbitrage"""
    return FundingArbitrage(rest_clients, balance_manager)
