"""
Spread Betting Strategy
Trades based on mean reversion of price spreads between correlated pairs
"""

import logging
from typing import Dict, Optional, Tuple
import asyncio
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)


class SpreadBettingStrategy:
    """
    Spread Betting / Pairs Trading Strategy
    
    Monitors spread between two correlated assets and trades when
    spread deviates significantly from historical mean.
    """
    
    def __init__(
        self,
        exchange_client,
        pair1: str,
        pair2: str,
        lookback_period: int = 100,
        entry_z_score: float = 2.0,
        exit_z_score: float = 0.5,
        position_size_usdt: float = 100.0
    ):
        self.exchange = exchange_client
        self.pair1 = pair1
        self.pair2 = pair2
        self.lookback_period = lookback_period
        self.entry_z_score = entry_z_score
        self.exit_z_score = exit_z_score
        self.position_size = position_size_usdt
        
        self.spread_history = deque(maxlen=lookback_period)
        self.position: Optional[str] = None  # 'long_spread' or 'short_spread'
        self.entry_spread = None
        self.running = False
        
    async def start(self):
        """Start strategy"""
        self.running = True
        logger.info(f"Starting spread betting: {self.pair1} vs {self.pair2}")
        
        while self.running:
            try:
                await self._analyze_and_trade()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in spread betting: {e}")
                await asyncio.sleep(10)
    
    def stop(self):
        """Stop strategy"""
        self.running = False
    
    async def _analyze_and_trade(self):
        """Analyze spread and execute trades"""
        # Fetch prices
        price1 = await self._get_price(self.pair1)
        price2 = await self._get_price(self.pair2)
        
        if not price1 or not price2:
            return
        
        # Calculate spread
        spread = price1 / price2
        self.spread_history.append(spread)
        
        if len(self.spread_history) < self.lookback_period:
            logger.info(f"Building history: {len(self.spread_history)}/{self.lookback_period}")
            return
        
        # Calculate z-score
        mean_spread = np.mean(self.spread_history)
        std_spread = np.std(self.spread_history)
        
        if std_spread == 0:
            return
        
        z_score = (spread - mean_spread) / std_spread
        
        logger.info(f"Spread: {spread:.6f}, Mean: {mean_spread:.6f}, Z-score: {z_score:.2f}")
        
        # Trading logic
        if self.position is None:
            await self._check_entry(z_score, spread, price1, price2)
        else:
            await self._check_exit(z_score, spread, price1, price2)
    
    async def _check_entry(self, z_score: float, spread: float, price1: float, price2: float):
        """Check for entry signals"""
        if z_score > self.entry_z_score:
            # Spread too high -> short spread (sell pair1, buy pair2)
            await self._enter_short_spread(price1, price2)
            self.position = 'short_spread'
            self.entry_spread = spread
            logger.info(f"Entered SHORT spread at z-score {z_score:.2f}")
            
        elif z_score < -self.entry_z_score:
            # Spread too low -> long spread (buy pair1, sell pair2)
            await self._enter_long_spread(price1, price2)
            self.position = 'long_spread'
            self.entry_spread = spread
            logger.info(f"Entered LONG spread at z-score {z_score:.2f}")
    
    async def _check_exit(self, z_score: float, spread: float, price1: float, price2: float):
        """Check for exit signals"""
        # Exit when z-score returns to near zero
        if abs(z_score) < self.exit_z_score:
            await self._close_position(price1, price2)
            
            profit = self._calculate_profit(spread)
            logger.info(f"Closed {self.position} at z-score {z_score:.2f}, profit: {profit:.2f} USDT")
            
            self.position = None
            self.entry_spread = None
    
    async def _enter_long_spread(self, price1: float, price2: float):
        """Enter long spread position (buy pair1, sell pair2)"""
        try:
            amount1 = self.position_size / price1
            amount2 = self.position_size / price2
            
            # Buy pair1
            await self.exchange.create_market_buy_order(self.pair1, amount1)
            # Sell pair2
            await self.exchange.create_market_sell_order(self.pair2, amount2)
            
        except Exception as e:
            logger.error(f"Failed to enter long spread: {e}")
    
    async def _enter_short_spread(self, price1: float, price2: float):
        """Enter short spread position (sell pair1, buy pair2)"""
        try:
            amount1 = self.position_size / price1
            amount2 = self.position_size / price2
            
            # Sell pair1
            await self.exchange.create_market_sell_order(self.pair1, amount1)
            # Buy pair2
            await self.exchange.create_market_buy_order(self.pair2, amount2)
            
        except Exception as e:
            logger.error(f"Failed to enter short spread: {e}")
    
    async def _close_position(self, price1: float, price2: float):
        """Close current position"""
        try:
            amount1 = self.position_size / price1
            amount2 = self.position_size / price2
            
            if self.position == 'long_spread':
                # Reverse: sell pair1, buy pair2
                await self.exchange.create_market_sell_order(self.pair1, amount1)
                await self.exchange.create_market_buy_order(self.pair2, amount2)
            else:
                # Reverse: buy pair1, sell pair2
                await self.exchange.create_market_buy_order(self.pair1, amount1)
                await self.exchange.create_market_sell_order(self.pair2, amount2)
                
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
    
    def _calculate_profit(self, current_spread: float) -> float:
        """Calculate profit from spread movement"""
        if not self.entry_spread or self.entry_spread == 0:
            return 0.0
        
        spread_change = (current_spread - self.entry_spread) / self.entry_spread
        
        if self.position == 'long_spread':
            return self.position_size * spread_change
        else:
            return self.position_size * (-spread_change)
    
    async def _get_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return (ticker['bid'] + ticker['ask']) / 2
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Get strategy statistics"""
        return {
            'pair1': self.pair1,
            'pair2': self.pair2,
            'position': self.position,
            'spread_history_len': len(self.spread_history),
            'current_spread': self.spread_history[-1] if self.spread_history else None,
            'entry_spread': self.entry_spread
        }
