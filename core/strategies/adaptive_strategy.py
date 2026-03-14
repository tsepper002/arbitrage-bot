"""
Adaptive Strategy - Self-adjusting strategy
Adapts parameters based on market conditions
"""
import logging
from typing import Dict, List
import time

logger = logging.getLogger(__name__)

class AdaptiveStrategy:
    """Self-adapting trading strategy"""
    
    def __init__(self, price_store, rest_clients, balance_manager, risk_manager):
        self.price_store = price_store
        self.rest_clients = rest_clients
        self.balance_manager = balance_manager
        self.risk_manager = risk_manager
        self.parameters = {
            'min_roi': 0.0003,
            'max_exposure': 500,
            'position_size': 100
        }
        self.performance_history = []
        logger.info("✅ AdaptiveStrategy initialized")
    
    def adapt_parameters(self, market_regime: str, recent_performance: float):
        """Adapt strategy parameters based on conditions"""
        try:
            # Adjust based on market regime
            if market_regime == 'VOLATILE':
                # In volatile markets, require higher ROI
                self.parameters['min_roi'] = 0.0005
                self.parameters['position_size'] = 75  # Reduce size
            elif market_regime == 'TRENDING':
                # In trending markets, can be more aggressive
                self.parameters['min_roi'] = 0.0002
                self.parameters['position_size'] = 125
            elif market_regime == 'RANGING':
                # In ranging markets, standard parameters
                self.parameters['min_roi'] = 0.0003
                self.parameters['position_size'] = 100
            
            # Adjust based on recent performance
            if recent_performance < 0:
                # If losing, reduce risk
                self.parameters['position_size'] *= 0.8
                self.parameters['min_roi'] *= 1.2
            elif recent_performance > 0.05:  # Good performance
                # If winning well, can slightly increase
                self.parameters['position_size'] *= 1.1
            
            # Keep within bounds
            self.parameters['position_size'] = max(50, min(200, self.parameters['position_size']))
            self.parameters['min_roi'] = max(0.0001, min(0.001, self.parameters['min_roi']))
            
            logger.info(f"Adapted parameters: {self.parameters}")
            
        except Exception as e:
            logger.error(f"Error adapting parameters: {e}")
    
    def get_parameters(self) -> Dict:
        """Get current parameters"""
        return self.parameters.copy()
    
    def record_performance(self, pnl: float, trade_count: int):
        """Record performance for adaptation"""
        try:
            self.performance_history.append({
                'pnl': pnl,
                'trades': trade_count,
                'timestamp': time.time()
            })
            
            # Keep recent history
            if len(self.performance_history) > 100:
                self.performance_history = self.performance_history[-50:]
                
        except Exception as e:
            logger.error(f"Error recording performance: {e}")

def get_adaptive_strategy(price_store, rest_clients, balance_manager, risk_manager):
    """Factory function"""
    return AdaptiveStrategy(price_store, rest_clients, balance_manager, risk_manager)
