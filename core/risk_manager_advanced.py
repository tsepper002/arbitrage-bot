"""Advanced risk manager with dynamic limits."""
import logging
from typing import Dict
import math

logger = logging.getLogger(__name__)

class RiskManagerAdvanced:
    """Advanced risk management."""
    
    def __init__(self, max_position_pct=10, max_loss_pct=5):
        self.max_position_pct = max_position_pct
        self.max_loss_pct = max_loss_pct
        self.logger = logging.getLogger(__name__)
        self.volatility_multiplier = 1.0
    
    def calculate_var(self, returns: list, confidence=0.95) -> float:
        """Calculate Value at Risk."""
        if not returns:
            return 0.0
        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        return abs(sorted_returns[index]) if index < len(sorted_returns) else 0.0
    
    def calculate_position_size(self, capital: float, volatility: float) -> float:
        """Calculate position size based on volatility."""
        base_size = capital * (self.max_position_pct / 100)
        volatility_adj = 1.0 / (1.0 + volatility)
        return base_size * volatility_adj
    
    def adjust_for_volatility(self, volatility: float):
        """Adjust limits based on market volatility."""
        if volatility > 0.5:  # High volatility
            self.volatility_multiplier = 0.5
        elif volatility > 0.3:  # Medium volatility
            self.volatility_multiplier = 0.75
        else:  # Low volatility
            self.volatility_multiplier = 1.0
    
    def check_limits(self, position_value: float, capital: float) -> bool:
        """Check if position is within limits."""
        position_pct = (position_value / capital * 100) if capital > 0 else 0
        adjusted_max = self.max_position_pct * self.volatility_multiplier
        return position_pct <= adjusted_max
    
    def kelly_criterion(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate Kelly criterion for position sizing."""
        if avg_loss == 0 or win_rate <= 0:
            return 0.0
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p
        kelly = (b * p - q) / b
        return max(0, min(kelly, 0.25))  # Cap at 25%
