"""
Volatility Forecaster - Predicts future volatility
Uses GARCH-like models to forecast volatility
"""
import logging
import numpy as np
from typing import Dict, List
from collections import deque
import time

logger = logging.getLogger(__name__)

class VolatilityForecaster:
    """Forecasts volatility for trading pairs"""
    
    def __init__(self, lookback_period: int = 100):
        self.lookback_period = lookback_period
        self.price_history = {}  # symbol -> deque of prices
        self.volatility_forecasts = {}  # symbol -> (timestamp, forecast)
        logger.info("✅ VolatilityForecaster initialized")
    
    def forecast(self, symbol: str, current_price: float, horizon: int = 10) -> float:
        """Forecast volatility for given horizon (in periods)"""
        try:
            # Check cache
            if symbol in self.volatility_forecasts:
                cached_time, cached_forecast = self.volatility_forecasts[symbol]
                if time.time() - cached_time < 300:  # 5 minute cache
                    return cached_forecast
            
            # Initialize history
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=self.lookback_period)
            
            # Add current price
            self.price_history[symbol].append(current_price)
            
            # Need enough data
            if len(self.price_history[symbol]) < 20:
                return 0.01  # Default 1% volatility
            
            prices = list(self.price_history[symbol])
            
            # Calculate returns
            returns = np.diff(prices) / prices[:-1]
            
            # Simple volatility forecast: exponentially weighted std
            weights = np.exp(np.linspace(-1, 0, len(returns)))
            weights = weights / weights.sum()
            weighted_variance = np.average(returns**2, weights=weights)
            volatility = np.sqrt(weighted_variance)
            
            # Adjust for horizon (square root of time rule)
            forecast = volatility * np.sqrt(horizon)
            
            self.volatility_forecasts[symbol] = (time.time(), forecast)
            return forecast
            
        except Exception as e:
            logger.error(f"Error forecasting volatility: {e}")
            return 0.01  # Default 1% volatility
    
    def get_current_volatility(self, symbol: str) -> float:
        """Get current realized volatility"""
        try:
            if symbol not in self.price_history or len(self.price_history[symbol]) < 20:
                return 0.01
            
            prices = list(self.price_history[symbol])
            returns = np.diff(prices) / prices[:-1]
            return np.std(returns)
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 0.01

def get_volatility_forecaster():
    """Factory function"""
    return VolatilityForecaster()
