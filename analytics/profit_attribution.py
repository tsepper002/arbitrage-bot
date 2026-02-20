"""Profit attribution analysis."""
import logging
from typing import Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)

class ProfitAttributionAnalyzer:
    """Analyze profit attribution across strategies and exchanges."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.trades = []
    
    def add_trade(self, trade: Dict):
        """Add trade for analysis."""
        self.trades.append(trade)
    
    def by_strategy(self) -> Dict:
        """Profit attribution by strategy."""
        by_strategy = defaultdict(float)
        for trade in self.trades:
            strategy = trade.get('strategy', 'unknown')
            profit = trade.get('profit', 0)
            by_strategy[strategy] += profit
        return dict(by_strategy)
    
    def by_exchange(self) -> Dict:
        """Profit attribution by exchange."""
        by_exchange = defaultdict(float)
        for trade in self.trades:
            exchange = trade.get('exchange', 'unknown')
            profit = trade.get('profit', 0)
            by_exchange[exchange] += profit
        return dict(by_exchange)
    
    def by_symbol(self) -> Dict:
        """Profit attribution by symbol."""
        by_symbol = defaultdict(float)
        for trade in self.trades:
            symbol = trade.get('symbol', 'unknown')
            profit = trade.get('profit', 0)
            by_symbol[symbol] += profit
        return dict(by_symbol)
    
    def time_based_attribution(self, period='hour') -> Dict:
        """Time-based profit attribution."""
        # Simplified - just total profit
        total = sum(t.get('profit', 0) for t in self.trades)
        return {period: total}
