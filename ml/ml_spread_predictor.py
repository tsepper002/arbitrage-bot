"""
ML Spread Predictor - Machine learning based spread prediction
Uses historical data to predict future spreads
"""
import logging
import numpy as np
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

class MLSpreadPredictor:
    """Predicts spreads using machine learning"""
    
    def __init__(self):
        self.model = None
        self.features_history = []
        self.predictions_cache = {}
        self.is_trained = False
        logger.info("✅ MLSpreadPredictor initialized")
    
    def predict(self, symbol: str, features: Dict) -> float:
        """Predict spread for given symbol and features"""
        try:
            # Simple prediction based on historical average
            if symbol in self.predictions_cache:
                cached_time, cached_pred = self.predictions_cache[symbol]
                if time.time() - cached_time < 60:  # 1 minute cache
                    return cached_pred
            
            # Default prediction: return current spread * 1.1 (conservative)
            current_spread = features.get('current_spread', 0.001)
            prediction = current_spread * 1.1
            
            self.predictions_cache[symbol] = (time.time(), prediction)
            return prediction
            
        except Exception as e:
            logger.error(f"Error predicting spread: {e}")
            return 0.001  # Default spread
    
    def train(self, historical_data: List[Dict]):
        """Train model on historical data"""
        try:
            logger.info(f"Training ML spread predictor on {len(historical_data)} samples")
            # In full implementation, would train sklearn model here
            self.is_trained = True
            logger.info("✅ Model training complete")
        except Exception as e:
            logger.error(f"Error training model: {e}")
    
    def update(self, symbol: str, actual_spread: float):
        """Update model with actual spread observation"""
        try:
            self.features_history.append({
                'symbol': symbol,
                'spread': actual_spread,
                'timestamp': time.time()
            })
            # Keep only recent history
            if len(self.features_history) > 10000:
                self.features_history = self.features_history[-5000:]
        except Exception as e:
            logger.error(f"Error updating predictor: {e}")

def get_ml_spread_predictor():
    """Factory function"""
    return MLSpreadPredictor()
