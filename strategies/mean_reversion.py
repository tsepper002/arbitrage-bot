"""
Mean Reversion Strategy - Statistical mean reversion
Trades when prices deviate from mean and revert
"""
import logging
from typing import Dict, List
import numpy as np
from collections import deque
import time

logger = logging.getLogger(__name__)

class MeanReversion:
    """Mean reversion trading strategy"""
    
    def __init__(self, price_store, rest_clients, balance_manager, lookback: int = 100):
        self.price_store = price_store
        self.rest_clients = rest_clients
        self.balance_manager = balance_manager
        self.lookback = lookback
        self.price_history = {}
        self.positions = []
        logger.info("✅ MeanReversion strategy initialized")
    
    def calculate_zscore(self, symbol: str, current_price: float) -> float:
        """Calculate Z-score for price"""
        try:
            # Initialize history
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=self.lookback)
            
            # Add current price
            self.price_history[symbol].append(current_price)
            
            # Need enough history
            if len(self.price_history[symbol]) < 20:
                return 0.0
            
            prices = list(self.price_history[symbol])
            mean = np.mean(prices)
            std = np.std(prices)
            
            if std == 0:
                return 0.0
            
            zscore = (current_price - mean) / std
            return zscore
            
        except Exception as e:
            logger.error(f"Error calculating Z-score: {e}")
            return 0.0
    
    def find_opportunities(self, symbol: str, current_price: float) -> List[Dict]:
        """Find mean reversion opportunities"""
        try:
            zscore = self.calculate_zscore(symbol, current_price)
            
            opportunities = []
            
            # Extreme deviation signals mean reversion
            if zscore > 2.0:  # Price too high
                opportunities.append({
                    'type': 'short',
                    'symbol': symbol,
                    'current_price': current_price,
                    'zscore': zscore,
                    'signal': 'SELL',
                    'confidence': min(abs(zscore) / 4, 1.0),
                    'timestamp': time.time()
                })
            elif zscore < -2.0:  # Price too low
                opportunities.append({
                    'type': 'long',
                    'symbol': symbol,
                    'current_price': current_price,
                    'zscore': zscore,
                    'signal': 'BUY',
                    'confidence': min(abs(zscore) / 4, 1.0),
                    'timestamp': time.time()
                })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Error finding mean reversion opportunities: {e}")
            return []
    
    def should_close_position(self, symbol: str, current_price: float, entry_price: float, side: str) -> bool:
        """Check if position should be closed (price reverted)"""
        try:
            zscore = self.calculate_zscore(symbol, current_price)
            
            # Close if Z-score near zero (reverted to mean)
            if abs(zscore) < 0.5:
                return True
            
            # Or if price moved 2% in profit direction
            if side == 'long' and current_price > entry_price * 1.02:
                return True
            if side == 'short' and current_price < entry_price * 0.98:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking position closure: {e}")
            return False

def get_mean_reversion(price_store, rest_clients, balance_manager):
    """Factory function"""
    return MeanReversion(price_store, rest_clients, balance_manager)
