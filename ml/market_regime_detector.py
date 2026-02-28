"""
Market Regime Detector - Detects market conditions
Identifies trending, ranging, volatile, or calm markets
"""
import logging
import numpy as np
from typing import Dict, List
from collections import deque
import time

logger = logging.getLogger(__name__)

class MarketRegimeDetector:
    """Detects current market regime"""
    
    REGIMES = ['TRENDING_UP', 'TRENDING_DOWN', 'RANGING', 'VOLATILE', 'CALM']
    
    def __init__(self, lookback_period: int = 100):
        self.lookback_period = lookback_period
        self.price_history = {}  # symbol -> deque of prices
        self.current_regime = {}  # symbol -> regime
        logger.info("✅ MarketRegimeDetector initialized")
    
    def detect(self, symbol: str, current_price: float) -> str:
        """Detect market regime for symbol"""
        try:
            # Initialize history for symbol
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=self.lookback_period)
                self.current_regime[symbol] = 'CALM'
            
            # Add current price
            self.price_history[symbol].append(current_price)
            
            # Need enough data
            if len(self.price_history[symbol]) < 20:
                return 'CALM'
            
            prices = list(self.price_history[symbol])
            
            # Guard against zero prices
            if prices[0] <= 0 or any(p <= 0 for p in prices):
                return 'NORMAL'
            
            # Calculate metrics
            returns = np.diff(prices) / prices[:-1]
            volatility = np.std(returns) if len(returns) > 0 else 0
            trend = (prices[-1] - prices[0]) / prices[0]
            
            # Detect regime
            if volatility > 0.02:  # High volatility
                regime = 'VOLATILE'
            elif abs(trend) < 0.005:  # Low trend
                regime = 'RANGING'
            elif trend > 0.01:  # Strong uptrend
                regime = 'TRENDING_UP'
            elif trend < -0.01:  # Strong downtrend
                regime = 'TRENDING_DOWN'
            else:
                regime = 'CALM'
            
            self.current_regime[symbol] = regime
            return regime
            
        except Exception as e:
            logger.error(f"Error detecting regime: {e}")
            return 'CALM'
    
    def get_regime(self, symbol: str) -> str:
        """Get current regime for symbol"""
        return self.current_regime.get(symbol, 'CALM')
    
    def get_all_regimes(self) -> Dict[str, str]:
        """Get regimes for all symbols"""
        return self.current_regime.copy()

def get_market_regime_detector():
    """Factory function"""
    return MarketRegimeDetector()
