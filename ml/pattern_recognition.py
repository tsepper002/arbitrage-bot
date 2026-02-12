"""Pattern recognition for technical analysis."""
import logging
from typing import List, Dict
import numpy as np

logger = logging.getLogger(__name__)

class PatternRecognition:
    """Recognize chart patterns and technical indicators."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.patterns = []
    
    def detect_support_resistance(self, prices: List[float]) -> Dict:
        """Detect support and resistance levels."""
        if len(prices) < 3:
            return {'support': [], 'resistance': []}
        
        # Simple algorithm: find local mins and maxs
        support = []
        resistance = []
        
        for i in range(1, len(prices) - 1):
            if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                support.append(prices[i])
            elif prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                resistance.append(prices[i])
        
        return {
            'support': support,
            'resistance': resistance
        }
    
    def detect_trend(self, prices: List[float]) -> str:
        """Detect trend direction."""
        if len(prices) < 2:
            return 'neutral'
        
        first_half = np.mean(prices[:len(prices)//2])
        second_half = np.mean(prices[len(prices)//2:])
        
        if second_half > first_half * 1.02:
            return 'uptrend'
        elif second_half < first_half * 0.98:
            return 'downtrend'
        else:
            return 'sideways'
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI indicator."""
        if len(prices) < period + 1:
            return 50.0
        
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [c if c > 0 else 0 for c in changes[-period:]]
        losses = [-c if c < 0 else 0 for c in changes[-period:]]
        
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def find_patterns(self, prices: List[float]) -> List[Dict]:
        """Find chart patterns."""
        patterns_found = []
        
        # Check for double top/bottom
        if len(prices) >= 5:
            if abs(prices[0] - prices[4]) < 0.01 * prices[0]:
                patterns_found.append({
                    'type': 'double_top_bottom',
                    'confidence': 0.7
                })
        
        return patterns_found
