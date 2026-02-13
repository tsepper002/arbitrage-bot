"""Risk Analytics - VaR, CVaR, risk metrics"""
import logging
import numpy as np
from typing import Dict, List
from collections import deque

logger = logging.getLogger(__name__)

class RiskAnalytics:
    def __init__(self, lookback_periods: int = 100):
        self.lookback = lookback_periods
        self.returns = deque(maxlen=lookback_periods)
        self.positions = deque(maxlen=lookback_periods)
        self.exposures = deque(maxlen=lookback_periods)
        
    def add_return(self, return_value: float):
        """Add a return data point"""
        self.returns.append(return_value)
        
    def add_position(self, position_size: float):
        """Add position size"""
        self.positions.append(position_size)
        
    def add_exposure(self, exposure: float):
        """Add exposure amount"""
        self.exposures.append(exposure)
        
    def calculate_var(self, confidence_level: float = 0.95) -> float:
        """Calculate Value at Risk"""
        if len(self.returns) < 10:
            return 0.0
            
        returns_array = np.array(self.returns)
        var = np.percentile(returns_array, (1 - confidence_level) * 100)
        return abs(var)
        
    def calculate_cvar(self, confidence_level: float = 0.95) -> float:
        """Calculate Conditional Value at Risk (Expected Shortfall)"""
        if len(self.returns) < 10:
            return 0.0
            
        returns_array = np.array(self.returns)
        var_threshold = np.percentile(returns_array, (1 - confidence_level) * 100)
        
        tail_losses = returns_array[returns_array <= var_threshold]
        cvar = np.mean(tail_losses) if len(tail_losses) > 0 else 0.0
        
        return abs(cvar)
        
    def calculate_volatility(self) -> float:
        """Calculate return volatility (annualized)"""
        if len(self.returns) < 2:
            return 0.0
            
        returns_array = np.array(self.returns)
        volatility = np.std(returns_array) * np.sqrt(252)  # Annualized
        return volatility
        
    def get_current_exposure(self) -> Dict:
        """Get current exposure metrics"""
        if not self.exposures:
            return {'current_exposure': 0.0, 'max_exposure': 0.0, 'avg_exposure': 0.0}
            
        exposures_array = np.array(self.exposures)
        
        return {
            'current_exposure': self.exposures[-1] if self.exposures else 0.0,
            'max_exposure': np.max(exposures_array),
            'avg_exposure': np.mean(exposures_array),
            'exposure_std': np.std(exposures_array)
        }
        
    def get_risk_metrics(self) -> Dict:
        """Get all risk metrics"""
        var_95 = self.calculate_var(0.95)
        var_99 = self.calculate_var(0.99)
        cvar_95 = self.calculate_cvar(0.95)
        volatility = self.calculate_volatility()
        exposure = self.get_current_exposure()
        
        return {
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'volatility': volatility,
            **exposure,
            'data_points': len(self.returns)
        }
        
    def stress_test(self, shock_pct: float = -0.10) -> Dict:
        """Run stress test with given shock"""
        if not self.positions or not self.exposures:
            return {'stressed_pnl': 0.0}
            
        current_exposure = self.exposures[-1] if self.exposures else 0.0
        stressed_pnl = current_exposure * shock_pct
        
        return {
            'shock_pct': shock_pct * 100,
            'current_exposure': current_exposure,
            'stressed_pnl': stressed_pnl
        }
