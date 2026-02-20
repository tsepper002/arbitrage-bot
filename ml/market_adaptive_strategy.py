"""
Market Adaptive Strategy Module

This module implements an adaptive trading strategy that automatically adjusts
parameters based on detected market conditions (trending, ranging, volatile).
Uses multiple technical indicators and machine learning for regime detection.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from collections import deque
import pandas as pd

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime types"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    BREAKOUT = "breakout"


@dataclass
class RegimeParameters:
    """Parameters for each market regime"""
    threshold: float
    lookback: int
    sensitivity: float
    position_size: float
    stop_loss: float
    take_profit: float


class MarketAdaptiveStrategy:
    """
    Advanced market adaptive strategy that detects market regimes
    and automatically adjusts trading parameters.
    
    Features:
    - Multi-indicator regime detection
    - Dynamic parameter adjustment
    - Volatility-based position sizing
    - Trend strength measurement
    - Range detection with support/resistance
    """
    
    def __init__(self, lookback_period: int = 100, regime_change_threshold: int = 5):
        """
        Initialize the market adaptive strategy.
        
        Args:
            lookback_period: Number of candles to analyze
            regime_change_threshold: Min confirmations before regime change
        """
        self.logger = logging.getLogger(__name__)
        self.lookback_period = lookback_period
        self.regime_change_threshold = regime_change_threshold
        
        # Current state
        self.current_regime = MarketRegime.RANGING
        self.regime_confidence = 0.0
        self.regime_history = deque(maxlen=regime_change_threshold)
        
        # Performance tracking
        self.regime_performance = {regime: {'wins': 0, 'losses': 0} for regime in MarketRegime}
        
        # Regime-specific parameters
        self.regime_params = {
            MarketRegime.TRENDING_UP: RegimeParameters(
                threshold=0.2, lookback=50, sensitivity=1.8,
                position_size=0.8, stop_loss=0.015, take_profit=0.04
            ),
            MarketRegime.TRENDING_DOWN: RegimeParameters(
                threshold=0.2, lookback=50, sensitivity=1.8,
                position_size=0.8, stop_loss=0.015, take_profit=0.04
            ),
            MarketRegime.RANGING: RegimeParameters(
                threshold=0.5, lookback=100, sensitivity=1.0,
                position_size=0.5, stop_loss=0.01, take_profit=0.02
            ),
            MarketRegime.VOLATILE: RegimeParameters(
                threshold=0.7, lookback=30, sensitivity=0.5,
                position_size=0.3, stop_loss=0.025, take_profit=0.05
            ),
            MarketRegime.BREAKOUT: RegimeParameters(
                threshold=0.3, lookback=20, sensitivity=2.0,
                position_size=1.0, stop_loss=0.02, take_profit=0.06
            )
        }
        
        self.logger.info(f"Market Adaptive Strategy initialized with lookback={lookback_period}")
    
    def calculate_volatility(self, prices: List[float]) -> float:
        """Calculate normalized volatility"""
        if len(prices) < 2:
            return 0.0
        
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns)
        
        # Normalize by average price
        avg_price = np.mean(prices)
        normalized_vol = volatility / avg_price if avg_price != 0 else 0
        
        return normalized_vol
    
    def calculate_trend_strength(self, prices: List[float]) -> Tuple[float, str]:
        """
        Calculate trend strength and direction.
        
        Returns:
            Tuple of (strength, direction) where strength is 0-1
        """
        if len(prices) < 20:
            return 0.0, "neutral"
        
        # Linear regression for trend
        x = np.arange(len(prices))
        y = np.array(prices)
        
        # Calculate slope
        slope = np.polyfit(x, y, 1)[0]
        
        # Calculate R-squared for trend strength
        y_pred = np.polyval([slope, y[0]], x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Determine direction
        if slope > 0:
            direction = "up"
        elif slope < 0:
            direction = "down"
        else:
            direction = "neutral"
        
        return max(0, min(1, r_squared)), direction
    
    def detect_ranging_market(self, prices: List[float]) -> bool:
        """Detect if market is ranging using price bounds"""
        if len(prices) < 20:
            return False
        
        # Check if price stays within narrow range
        price_range = max(prices) - min(prices)
        avg_price = np.mean(prices)
        range_ratio = price_range / avg_price if avg_price != 0 else 0
        
        # Ranging if price stays within 3% range
        return range_ratio < 0.03
    
    def detect_breakout(self, prices: List[float], volumes: Optional[List[float]] = None) -> bool:
        """Detect potential breakout conditions"""
        if len(prices) < 50:
            return False
        
        # Recent price action
        recent_prices = prices[-20:]
        historical_prices = prices[-50:-20]
        
        # Check for range breakout
        recent_high = max(recent_prices)
        recent_low = min(recent_prices)
        hist_high = max(historical_prices)
        hist_low = min(historical_prices)
        
        # Breakout if recent action breaks historical range significantly
        upper_breakout = recent_high > hist_high * 1.015
        lower_breakout = recent_low < hist_low * 0.985
        
        # Volume confirmation if available
        volume_confirmed = True
        if volumes and len(volumes) >= 20:
            recent_volume = np.mean(volumes[-10:])
            hist_volume = np.mean(volumes[-30:-10])
            volume_confirmed = recent_volume > hist_volume * 1.3
        
        return (upper_breakout or lower_breakout) and volume_confirmed
    
    def detect_market_regime(self, prices: List[float], volumes: Optional[List[float]] = None) -> MarketRegime:
        """
        Detect current market regime using multiple indicators.
        
        Args:
            prices: List of recent prices
            volumes: Optional list of volumes
            
        Returns:
            Detected MarketRegime
        """
        if len(prices) < 20:
            return MarketRegime.RANGING
        
        # Calculate indicators
        volatility = self.calculate_volatility(prices)
        trend_strength, trend_direction = self.calculate_trend_strength(prices)
        is_ranging = self.detect_ranging_market(prices)
        is_breakout = self.detect_breakout(prices, volumes)
        
        # Regime detection logic
        if is_breakout:
            regime = MarketRegime.BREAKOUT
            confidence = 0.85
        elif volatility > 0.04:  # High volatility
            regime = MarketRegime.VOLATILE
            confidence = 0.7 + min(volatility * 5, 0.3)
        elif is_ranging:
            regime = MarketRegime.RANGING
            confidence = 0.75
        elif trend_strength > 0.6:  # Strong trend
            if trend_direction == "up":
                regime = MarketRegime.TRENDING_UP
            else:
                regime = MarketRegime.TRENDING_DOWN
            confidence = 0.6 + trend_strength * 0.4
        else:  # Default to ranging
            regime = MarketRegime.RANGING
            confidence = 0.5
        
        self.regime_confidence = confidence
        
        # Add to history for confirmation
        self.regime_history.append(regime)
        
        # Confirm regime change only if consistent
        if len(self.regime_history) >= self.regime_change_threshold:
            most_common = max(set(self.regime_history), key=list(self.regime_history).count)
            if most_common != self.current_regime:
                self.logger.info(f"Regime changed: {self.current_regime.value} -> {most_common.value} (confidence: {confidence:.2f})")
                self.current_regime = most_common
        
        return self.current_regime
    
    def adapt_parameters(self, regime: MarketRegime) -> RegimeParameters:
        """
        Get adapted parameters for the current regime.
        
        Args:
            regime: Current market regime
            
        Returns:
            RegimeParameters optimized for the regime
        """
        params = self.regime_params[regime]
        
        # Adjust based on regime performance
        performance = self.regime_performance[regime]
        total_trades = performance['wins'] + performance['losses']
        
        if total_trades > 10:
            win_rate = performance['wins'] / total_trades
            
            # Increase position size if performing well
            if win_rate > 0.6:
                params.position_size = min(params.position_size * 1.2, 1.0)
            elif win_rate < 0.4:
                params.position_size = max(params.position_size * 0.8, 0.2)
        
        return params
    
    def get_trading_signal(self, market_data: Dict) -> Dict:
        """
        Generate comprehensive trading signal based on current regime.
        
        Args:
            market_data: Dictionary with 'prices', optional 'volumes'
            
        Returns:
            Dictionary with trading signal and parameters
        """
        prices = market_data.get('prices', [])
        volumes = market_data.get('volumes')
        
        if len(prices) < self.lookback_period:
            prices_to_use = prices
        else:
            prices_to_use = prices[-self.lookback_period:]
        
        # Detect regime
        regime = self.detect_market_regime(prices_to_use, volumes)
        
        # Get adapted parameters
        params = self.adapt_parameters(regime)
        
        # Generate signal direction
        signal_direction = "neutral"
        if regime == MarketRegime.TRENDING_UP:
            signal_direction = "long"
        elif regime == MarketRegime.TRENDING_DOWN:
            signal_direction = "short"
        elif regime == MarketRegime.BREAKOUT:
            # Determine breakout direction
            if len(prices) >= 2:
                signal_direction = "long" if prices[-1] > prices[-2] else "short"
        elif regime == MarketRegime.RANGING:
            # Mean reversion in ranging market
            if len(prices) >= 50:
                avg = np.mean(prices[-50:])
                signal_direction = "long" if prices[-1] < avg else "short"
        
        return {
            'regime': regime.value,
            'direction': signal_direction,
            'confidence': self.regime_confidence,
            'parameters': {
                'threshold': params.threshold,
                'lookback': params.lookback,
                'sensitivity': params.sensitivity,
                'position_size': params.position_size,
                'stop_loss': params.stop_loss,
                'take_profit': params.take_profit
            },
            'indicators': {
                'volatility': self.calculate_volatility(prices_to_use),
                'trend_strength': self.calculate_trend_strength(prices_to_use)[0],
                'trend_direction': self.calculate_trend_strength(prices_to_use)[1]
            }
        }
    
    def update_performance(self, regime: MarketRegime, won: bool):
        """Update performance tracking for regime-based learning"""
        if won:
            self.regime_performance[regime]['wins'] += 1
        else:
            self.regime_performance[regime]['losses'] += 1
    
    def get_statistics(self) -> Dict:
        """Get strategy statistics"""
        stats = {
            'current_regime': self.current_regime.value,
            'confidence': self.regime_confidence,
            'performance_by_regime': {}
        }
        
        for regime, perf in self.regime_performance.items():
            total = perf['wins'] + perf['losses']
            win_rate = perf['wins'] / total if total > 0 else 0
            stats['performance_by_regime'][regime.value] = {
                'trades': total,
                'win_rate': win_rate,
                'wins': perf['wins'],
                'losses': perf['losses']
            }
        
        return stats
