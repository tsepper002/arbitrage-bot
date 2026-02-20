"""
Custom Indicators - Custom technical indicators
Implements custom trading indicators
"""
import logging
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

class CustomIndicators:
    """Custom technical indicators"""
    
    def __init__(self):
        logger.info("✅ CustomIndicators initialized")
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)"""
        try:
            if len(prices) < period + 1:
                return 50.0  # Neutral
            
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return 50.0
    
    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict:
        """Calculate Bollinger Bands"""
        try:
            if len(prices) < period:
                return {'upper': 0, 'middle': 0, 'lower': 0}
            
            recent = prices[-period:]
            middle = np.mean(recent)
            std = np.std(recent)
            
            return {
                'upper': middle + (std_dev * std),
                'middle': middle,
                'lower': middle - (std_dev * std)
            }
            
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return {'upper': 0, 'middle': 0, 'lower': 0}
    
    def calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """Calculate MACD"""
        try:
            if len(prices) < slow:
                return {'macd': 0, 'signal': 0, 'histogram': 0}
            
            # Simple implementation
            fast_ema = np.mean(prices[-fast:])
            slow_ema = np.mean(prices[-slow:])
            macd_line = fast_ema - slow_ema
            signal_line = macd_line * 0.9  # Simplified
            histogram = macd_line - signal_line
            
            return {
                'macd': macd_line,
                'signal': signal_line,
                'histogram': histogram
            }
            
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return {'macd': 0, 'signal': 0, 'histogram': 0}

def get_custom_indicators():
    """Factory function"""
    return CustomIndicators()
