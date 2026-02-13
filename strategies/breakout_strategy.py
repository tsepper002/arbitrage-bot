"""
Breakout Trading Strategy
Implements support/resistance detection and breakout trading logic
"""

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class BreakoutStrategy:
    """
    Breakout trading strategy with support/resistance detection
    """
    
    def __init__(self, config: Dict = None):
        """Initialize breakout strategy"""
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        self.breakout_threshold = self.config.get('breakout_threshold', 0.001)
        self.min_touches = self.config.get('min_touches', 3)
        
        self.support_levels = {}
        self.resistance_levels = {}
        self.breakout_signals = []
        self.price_history = defaultdict(list)
        self.volume_history = defaultdict(list)
        
        logger.info("Breakout strategy initialized")
    
    def find_support_resistance(self, symbol: str, prices: List[float], 
                                tolerance: float = 0.02) -> Tuple[List[float], List[float]]:
        """
        Find support and resistance levels using local extrema
        
        Args:
            symbol: Trading symbol
            prices: Price history
            tolerance: Clustering tolerance
            
        Returns:
            Tuple of (support_levels, resistance_levels)
        """
        if len(prices) < self.lookback_period:
            return [], []
        
        # Find local minima (support)
        supports = []
        for i in range(2, len(prices) - 2):
            if (prices[i] < prices[i-1] and prices[i] < prices[i-2] and
                prices[i] < prices[i+1] and prices[i] < prices[i+2]):
                supports.append(prices[i])
        
        # Find local maxima (resistance)
        resistances = []
        for i in range(2, len(prices) - 2):
            if (prices[i] > prices[i-1] and prices[i] > prices[i-2] and
                prices[i] > prices[i+1] and prices[i] > prices[i+2]):
                resistances.append(prices[i])
        
        # Cluster nearby levels
        support_clusters = self._cluster_levels(supports, tolerance)
        resistance_clusters = self._cluster_levels(resistances, tolerance)
        
        # Filter by number of touches
        valid_supports = [s for s in support_clusters 
                         if self._count_touches(prices, s, tolerance) >= self.min_touches]
        valid_resistances = [r for r in resistance_clusters 
                            if self._count_touches(prices, r, tolerance) >= self.min_touches]
        
        self.support_levels[symbol] = valid_supports
        self.resistance_levels[symbol] = valid_resistances
        
        return valid_supports, valid_resistances
    
    def _cluster_levels(self, levels: List[float], tolerance: float) -> List[float]:
        """Cluster nearby price levels"""
        if not levels:
            return []
        
        sorted_levels = sorted(levels)
        clusters = []
        current_cluster = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            if abs(level - current_cluster[-1]) / current_cluster[-1] <= tolerance:
                current_cluster.append(level)
            else:
                clusters.append(np.mean(current_cluster))
                current_cluster = [level]
        
        clusters.append(np.mean(current_cluster))
        return clusters
    
    def _count_touches(self, prices: List[float], level: float, 
                       tolerance: float) -> int:
        """Count how many times price touched a level"""
        touches = 0
        for price in prices:
            if abs(price - level) / level <= tolerance:
                touches += 1
        return touches
    
    def detect_breakout(self, symbol: str, current_price: float, 
                       current_volume: float, avg_volume: float) -> Optional[Dict]:
        """
        Detect breakout from support/resistance
        
        Args:
            symbol: Trading symbol
            current_price: Current price
            current_volume: Current volume
            avg_volume: Average volume
            
        Returns:
            Breakout signal dict or None
        """
        if symbol not in self.support_levels or symbol not in self.resistance_levels:
            return None
        
        # Check for resistance breakout (bullish)
        for resistance in self.resistance_levels[symbol]:
            if current_price > resistance * (1 + self.breakout_threshold):
                # Volume confirmation
                if current_volume > avg_volume * self.volume_threshold:
                    signal = {
                        'type': 'BREAKOUT_BUY',
                        'symbol': symbol,
                        'price': current_price,
                        'level': resistance,
                        'volume_ratio': current_volume / avg_volume,
                        'timestamp': datetime.now(),
                        'confidence': self._calculate_confidence(
                            current_price, resistance, current_volume, avg_volume
                        )
                    }
                    self.breakout_signals.append(signal)
                    logger.info(f"Breakout BUY signal: {symbol} @ {current_price}")
                    return signal
        
        # Check for support breakdown (bearish)
        for support in self.support_levels[symbol]:
            if current_price < support * (1 - self.breakout_threshold):
                if current_volume > avg_volume * self.volume_threshold:
                    signal = {
                        'type': 'BREAKOUT_SELL',
                        'symbol': symbol,
                        'price': current_price,
                        'level': support,
                        'volume_ratio': current_volume / avg_volume,
                        'timestamp': datetime.now(),
                        'confidence': self._calculate_confidence(
                            current_price, support, current_volume, avg_volume
                        )
                    }
                    self.breakout_signals.append(signal)
                    logger.info(f"Breakout SELL signal: {symbol} @ {current_price}")
                    return signal
        
        return None
    
    def _calculate_confidence(self, price: float, level: float, 
                             volume: float, avg_volume: float) -> float:
        """Calculate breakout confidence score"""
        # Distance from level
        distance_score = min(abs(price - level) / level / 0.05, 1.0)
        
        # Volume score
        volume_score = min(volume / avg_volume / 3.0, 1.0)
        
        # Combined confidence
        confidence = (distance_score * 0.4 + volume_score * 0.6)
        return round(confidence, 3)
    
    def is_false_breakout(self, symbol: str, current_price: float,
                         breakout_price: float, time_elapsed: int) -> bool:
        """
        Check if breakout was false (price returned below/above level)
        
        Args:
            symbol: Trading symbol
            current_price: Current price
            breakout_price: Price at breakout
            time_elapsed: Minutes since breakout
            
        Returns:
            True if false breakout detected
        """
        if time_elapsed < 5:
            return False
        
        # For bullish breakout, check if price fell back
        if breakout_price > current_price:
            if current_price < breakout_price * 0.995:
                logger.warning(f"False breakout detected: {symbol}")
                return True
        
        # For bearish breakdown, check if price recovered
        elif breakout_price < current_price:
            if current_price > breakout_price * 1.005:
                logger.warning(f"False breakdown detected: {symbol}")
                return True
        
        return False
    
    def update_history(self, symbol: str, price: float, volume: float):
        """Update price and volume history"""
        self.price_history[symbol].append(price)
        self.volume_history[symbol].append(volume)
        
        # Keep only recent history
        if len(self.price_history[symbol]) > self.lookback_period:
            self.price_history[symbol] = self.price_history[symbol][-self.lookback_period:]
            self.volume_history[symbol] = self.volume_history[symbol][-self.lookback_period:]
    
    def analyze(self, symbol: str, price: float, volume: float) -> Optional[Dict]:
        """
        Main analysis method
        
        Args:
            symbol: Trading symbol
            price: Current price
            volume: Current volume
            
        Returns:
            Trading signal or None
        """
        # Update history
        self.update_history(symbol, price, volume)
        
        # Need enough history
        if len(self.price_history[symbol]) < self.lookback_period:
            return None
        
        # Find support/resistance levels
        supports, resistances = self.find_support_resistance(
            symbol, 
            self.price_history[symbol]
        )
        
        # Calculate average volume
        avg_volume = np.mean(self.volume_history[symbol])
        
        # Detect breakout
        signal = self.detect_breakout(symbol, price, volume, avg_volume)
        
        return signal
    
    def get_statistics(self) -> Dict:
        """Get strategy statistics"""
        return {
            'total_signals': len(self.breakout_signals),
            'buy_signals': sum(1 for s in self.breakout_signals if s['type'] == 'BREAKOUT_BUY'),
            'sell_signals': sum(1 for s in self.breakout_signals if s['type'] == 'BREAKOUT_SELL'),
            'avg_confidence': np.mean([s['confidence'] for s in self.breakout_signals]) if self.breakout_signals else 0,
            'tracked_symbols': len(self.price_history)
        }
