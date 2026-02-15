"""
Slippage Predictor - Predicts execution slippage
Helps optimize order sizes and timing
"""
import logging
import numpy as np
from typing import Dict, Optional
import time

logger = logging.getLogger(__name__)

class SlippagePredictor:
    """Predicts slippage for order execution"""
    
    def __init__(self):
        self.slippage_history = []
        self.predictions_cache = {}
        logger.info("✅ SlippagePredictor initialized")
    
    def predict(self, volume: float, orderbook: Dict, symbol: str = "BTC/USDT") -> float:
        """Predict slippage for given volume and orderbook"""
        try:
            # Check cache
            cache_key = f"{symbol}_{volume}"
            if cache_key in self.predictions_cache:
                cached_time, cached_pred = self.predictions_cache[cache_key]
                if time.time() - cached_time < 30:  # 30 second cache
                    return cached_pred
            
            # Calculate estimated slippage based on orderbook depth
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            if not bids or not asks:
                return 0.001  # 0.1% default slippage
            
            # Simple estimation: larger volume = more slippage
            total_liquidity = sum([float(b[1]) for b in bids[:10]]) + sum([float(a[1]) for a in asks[:10]])
            
            if total_liquidity == 0:
                slippage = 0.002
            else:
                slippage_ratio = min(volume / total_liquidity, 1.0)
                slippage = 0.0001 + (slippage_ratio * 0.005)  # 0.01% to 0.51%
            
            self.predictions_cache[cache_key] = (time.time(), slippage)
            return slippage
            
        except Exception as e:
            logger.error(f"Error predicting slippage: {e}")
            return 0.001  # Default 0.1% slippage
    
    def record_actual(self, symbol: str, volume: float, actual_slippage: float):
        """Record actual slippage for model improvement"""
        try:
            self.slippage_history.append({
                'symbol': symbol,
                'volume': volume,
                'slippage': actual_slippage,
                'timestamp': time.time()
            })
            # Keep recent history only
            if len(self.slippage_history) > 5000:
                self.slippage_history = self.slippage_history[-2500:]
        except Exception as e:
            logger.error(f"Error recording slippage: {e}")

def get_slippage_predictor():
    """Factory function"""
    return SlippagePredictor()
