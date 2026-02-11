"""
Statistical Arbitrage - Mean reversion and pair trading strategies
Identifies statistical relationships between assets for profit.
"""

import asyncio
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class StatArbOpportunity:
    """Statistical arbitrage opportunity."""
    pair: Tuple[str, str]  # (symbol1, symbol2)
    correlation: float
    current_spread: float
    mean_spread: float
    std_spread: float
    z_score: float
    signal: str  # 'long_pair', 'short_pair', or 'neutral'
    entry_price1: float
    entry_price2: float
    target_spread: float
    confidence: float
    timestamp: datetime


class StatisticalArbitrage:
    """
    Statistical arbitrage using mean reversion and cointegration.
    
    Features:
    - Pair trading (e.g., BTC/ETH correlation)
    - Z-score calculation
    - Mean reversion detection
    - Cointegration testing
    - Dynamic hedge ratios
    """
    
    def __init__(
        self,
        lookback_periods: int = 100,
        z_score_entry: float = 2.0,
        z_score_exit: float = 0.5,
        min_correlation: float = 0.7
    ):
        """
        Initialize statistical arbitrage.
        
        Args:
            lookback_periods: Number of periods for statistics
            z_score_entry: Z-score threshold for entry
            z_score_exit: Z-score threshold for exit
            min_correlation: Minimum correlation for pair trading
        """
        self.lookback_periods = lookback_periods
        self.z_score_entry = z_score_entry
        self.z_score_exit = z_score_exit
        self.min_correlation = min_correlation
        
        # Price history: symbol -> deque of prices
        self.price_history: Dict[str, deque] = {}
        
        # Spread history: (symbol1, symbol2) -> deque of spreads
        self.spread_history: Dict[Tuple[str, str], deque] = {}
        
        logger.info(f"StatisticalArbitrage initialized (lookback={lookback_periods})")
    
    async def update_price(self, symbol: str, price: float):
        """
        Update price for a symbol.
        
        Args:
            symbol: Trading symbol
            price: Current price
        """
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.lookback_periods)
        
        self.price_history[symbol].append(price)
    
    def _calculate_correlation(self, prices1: List[float], prices2: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(prices1) < 2 or len(prices2) < 2:
            return 0.0
        
        return float(np.corrcoef(prices1, prices2)[0, 1])
    
    def _calculate_spread(self, price1: float, price2: float, hedge_ratio: float = 1.0) -> float:
        """Calculate spread between two prices."""
        return price1 - (hedge_ratio * price2)
    
    def _calculate_z_score(self, current_spread: float, mean_spread: float, std_spread: float) -> float:
        """Calculate z-score of current spread."""
        if std_spread == 0:
            return 0.0
        
        return (current_spread - mean_spread) / std_spread
    
    async def find_pairs(self) -> List[Tuple[str, str, float]]:
        """
        Find correlated pairs suitable for pair trading.
        
        Returns:
            List of (symbol1, symbol2, correlation)
        """
        pairs = []
        symbols = list(self.price_history.keys())
        
        for i, symbol1 in enumerate(symbols):
            for symbol2 in symbols[i+1:]:
                prices1 = list(self.price_history[symbol1])
                prices2 = list(self.price_history[symbol2])
                
                # Need enough data
                if len(prices1) < 20 or len(prices2) < 20:
                    continue
                
                # Calculate correlation
                correlation = self._calculate_correlation(prices1, prices2)
                
                if abs(correlation) >= self.min_correlation:
                    pairs.append((symbol1, symbol2, correlation))
        
        # Sort by absolute correlation
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        
        return pairs
    
    async def calculate_hedge_ratio(self, symbol1: str, symbol2: str) -> float:
        """
        Calculate optimal hedge ratio using linear regression.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
        
        Returns:
            Hedge ratio (beta)
        """
        prices1 = np.array(list(self.price_history[symbol1]))
        prices2 = np.array(list(self.price_history[symbol2]))
        
        if len(prices1) < 2 or len(prices2) < 2:
            return 1.0
        
        # Simple linear regression: prices1 = alpha + beta * prices2
        beta = np.cov(prices1, prices2)[0, 1] / np.var(prices2)
        
        return float(beta)
    
    async def find_opportunities(self) -> List[StatArbOpportunity]:
        """
        Find statistical arbitrage opportunities.
        
        Returns:
            List of opportunities
        """
        opportunities = []
        
        # Find correlated pairs
        pairs = await self.find_pairs()
        
        for symbol1, symbol2, correlation in pairs:
            # Need enough price history
            if len(self.price_history[symbol1]) < self.lookback_periods:
                continue
            if len(self.price_history[symbol2]) < self.lookback_periods:
                continue
            
            # Calculate hedge ratio
            hedge_ratio = await self.calculate_hedge_ratio(symbol1, symbol2)
            
            # Calculate historical spreads
            prices1 = list(self.price_history[symbol1])
            prices2 = list(self.price_history[symbol2])
            
            spreads = [
                self._calculate_spread(p1, p2, hedge_ratio)
                for p1, p2 in zip(prices1, prices2)
            ]
            
            # Calculate spread statistics
            mean_spread = float(np.mean(spreads))
            std_spread = float(np.std(spreads))
            current_spread = spreads[-1]
            
            # Calculate z-score
            z_score = self._calculate_z_score(current_spread, mean_spread, std_spread)
            
            # Determine signal
            signal = 'neutral'
            confidence = abs(z_score) / self.z_score_entry
            
            if z_score > self.z_score_entry:
                # Spread is too high - short the spread
                signal = 'short_pair'  # Sell symbol1, buy symbol2
            elif z_score < -self.z_score_entry:
                # Spread is too low - long the spread
                signal = 'long_pair'  # Buy symbol1, sell symbol2
            
            if signal != 'neutral':
                opportunity = StatArbOpportunity(
                    pair=(symbol1, symbol2),
                    correlation=correlation,
                    current_spread=current_spread,
                    mean_spread=mean_spread,
                    std_spread=std_spread,
                    z_score=z_score,
                    signal=signal,
                    entry_price1=prices1[-1],
                    entry_price2=prices2[-1],
                    target_spread=mean_spread,  # Target is mean reversion
                    confidence=min(confidence, 1.0),
                    timestamp=datetime.now()
                )
                
                opportunities.append(opportunity)
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x.confidence, reverse=True)
        
        return opportunities
    
    async def check_exit_signal(self, opportunity: StatArbOpportunity) -> bool:
        """
        Check if position should be exited.
        
        Args:
            opportunity: Original opportunity
        
        Returns:
            True if should exit
        """
        symbol1, symbol2 = opportunity.pair
        
        # Get current prices
        if symbol1 not in self.price_history or symbol2 not in self.price_history:
            return False
        
        current_price1 = list(self.price_history[symbol1])[-1]
        current_price2 = list(self.price_history[symbol2])[-1]
        
        # Calculate hedge ratio
        hedge_ratio = await self.calculate_hedge_ratio(symbol1, symbol2)
        
        # Calculate current spread
        current_spread = self._calculate_spread(current_price1, current_price2, hedge_ratio)
        
        # Calculate z-score
        z_score = self._calculate_z_score(
            current_spread,
            opportunity.mean_spread,
            opportunity.std_spread
        )
        
        # Exit if z-score has reverted to exit threshold
        return abs(z_score) <= self.z_score_exit
    
    async def execute_pair_trade(self, opportunity: StatArbOpportunity, amount: float) -> dict:
        """
        Execute pair trade.
        
        Args:
            opportunity: Opportunity to execute
            amount: Amount for symbol1
        
        Returns:
            Execution result
        """
        symbol1, symbol2 = opportunity.pair
        
        logger.info(
            f"Executing pair trade: {symbol1}/{symbol2}, "
            f"signal={opportunity.signal}, z-score={opportunity.z_score:.2f}"
        )
        
        try:
            # Calculate hedge ratio
            hedge_ratio = await self.calculate_hedge_ratio(symbol1, symbol2)
            amount2 = amount * hedge_ratio
            
            if opportunity.signal == 'long_pair':
                # Buy symbol1, sell symbol2
                result1 = await self._execute_trade(symbol1, 'buy', amount, opportunity.entry_price1)
                result2 = await self._execute_trade(symbol2, 'sell', amount2, opportunity.entry_price2)
            
            else:  # short_pair
                # Sell symbol1, buy symbol2
                result1 = await self._execute_trade(symbol1, 'sell', amount, opportunity.entry_price1)
                result2 = await self._execute_trade(symbol2, 'buy', amount2, opportunity.entry_price2)
            
            logger.info(f"Pair trade executed successfully")
            
            return {
                'success': True,
                'symbol1_result': result1,
                'symbol2_result': result2,
                'hedge_ratio': hedge_ratio,
                'entry_spread': opportunity.current_spread,
                'target_spread': opportunity.target_spread
            }
        
        except Exception as e:
            logger.error(f"Pair trade failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _execute_trade(self, symbol: str, side: str, amount: float, price: float) -> dict:
        """Execute single trade."""
        # Placeholder - integrate with actual exchange
        logger.info(f"Executing {side} {amount} {symbol} at ${price}")
        
        return {
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': price,
            'filled': amount
        }
    
    async def get_stats(self) -> dict:
        """Get statistical arbitrage statistics."""
        total_pairs_possible = len(self.price_history) * (len(self.price_history) - 1) // 2
        monitored_pairs = await self.find_pairs()
        
        return {
            'symbols_monitored': len(self.price_history),
            'pairs_possible': total_pairs_possible,
            'correlated_pairs': len(monitored_pairs),
            'lookback_periods': self.lookback_periods,
            'z_score_entry': self.z_score_entry,
            'z_score_exit': self.z_score_exit,
            'min_correlation': self.min_correlation
        }


# Global instance
_statistical_arbitrage: Optional[StatisticalArbitrage] = None


def get_statistical_arbitrage(lookback_periods: int = 100) -> StatisticalArbitrage:
    """
    Get statistical arbitrage instance.
    
    Args:
        lookback_periods: Number of periods for statistics
    
    Returns:
        StatisticalArbitrage instance
    """
    global _statistical_arbitrage
    
    if _statistical_arbitrage is None:
        _statistical_arbitrage = StatisticalArbitrage(lookback_periods=lookback_periods)
    
    return _statistical_arbitrage


# Usage example
"""
from core.statistical_arbitrage import get_statistical_arbitrage

stat_arb = get_statistical_arbitrage()

# Update prices over time
for i in range(150):
    btc_price = 50000 + np.random.randn() * 1000
    eth_price = 3000 + (btc_price - 50000) * 0.06 + np.random.randn() * 50
    
    await stat_arb.update_price('BTC/USDT', btc_price)
    await stat_arb.update_price('ETH/USDT', eth_price)

# Find correlated pairs
pairs = await stat_arb.find_pairs()
print(f"Found {len(pairs)} correlated pairs")

# Find opportunities
opportunities = await stat_arb.find_opportunities()

for opp in opportunities:
    print(f"Pair: {opp.pair}")
    print(f"Signal: {opp.signal}")
    print(f"Z-score: {opp.z_score:.2f}")
    print(f"Confidence: {opp.confidence:.2%}")

# Execute best opportunity
if opportunities:
    result = await stat_arb.execute_pair_trade(opportunities[0], amount=1.0)
    print(f"Result: {result}")
    
    # Later, check for exit
    should_exit = await stat_arb.check_exit_signal(opportunities[0])
    if should_exit:
        print("Exit signal detected - close position")
"""
