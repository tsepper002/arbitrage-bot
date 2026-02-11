"""Performance Tracker - Sharpe ratio, drawdown, returns"""
import logging
import numpy as np
from typing import Dict, List
from collections import deque

logger = logging.getLogger(__name__)

class PerformanceTracker:
    def __init__(self, lookback_days: int = 30):
        self.lookback = lookback_days * 24  # hours
        self.returns = deque(maxlen=self.lookback)
        self.equity_curve = deque(maxlen=self.lookback)
        self.initial_balance = 0.0
        self.current_balance = 0.0
        
    def set_initial_balance(self, balance: float):
        """Set starting balance"""
        self.initial_balance = balance
        self.current_balance = balance
        self.equity_curve.append((0, balance))
        
    def update_balance(self, balance: float):
        """Update current balance and calculate return"""
        if self.current_balance > 0:
            ret = (balance - self.current_balance) / self.current_balance
            self.returns.append(ret)
        
        self.current_balance = balance
        self.equity_curve.append((len(self.equity_curve), balance))
        
    def get_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio (annualized)"""
        if len(self.returns) < 2:
            return 0.0
            
        returns_array = np.array(self.returns)
        excess_returns = returns_array - (risk_free_rate / (365 * 24))
        
        if np.std(excess_returns) == 0:
            return 0.0
            
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(365 * 24)
        return sharpe
        
    def get_max_drawdown(self) -> Dict:
        """Calculate maximum drawdown"""
        if len(self.equity_curve) < 2:
            return {'max_drawdown': 0.0, 'max_drawdown_pct': 0.0}
            
        equity = np.array([e[1] for e in self.equity_curve])
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        
        max_dd = np.min(drawdown)
        max_dd_pct = max_dd * 100
        
        return {
            'max_drawdown': max_dd,
            'max_drawdown_pct': max_dd_pct
        }
        
    def get_total_return(self) -> Dict:
        """Calculate total and annualized returns"""
        if self.initial_balance == 0:
            return {'total_return': 0.0, 'total_return_pct': 0.0, 'annualized_return': 0.0}
            
        total_ret = (self.current_balance - self.initial_balance) / self.initial_balance
        total_ret_pct = total_ret * 100
        
        # Annualize based on time elapsed
        hours_elapsed = len(self.equity_curve)
        years_elapsed = hours_elapsed / (365 * 24)
        
        if years_elapsed > 0:
            annualized = (1 + total_ret) ** (1 / years_elapsed) - 1
        else:
            annualized = 0.0
            
        return {
            'total_return': total_ret,
            'total_return_pct': total_ret_pct,
            'annualized_return': annualized * 100
        }
        
    def get_statistics(self) -> Dict:
        """Get all performance statistics"""
        sharpe = self.get_sharpe_ratio()
        drawdown = self.get_max_drawdown()
        returns = self.get_total_return()
        
        return {
            **returns,
            'sharpe_ratio': sharpe,
            **drawdown,
            'current_balance': self.current_balance,
            'data_points': len(self.equity_curve)
        }
