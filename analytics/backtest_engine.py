"""Backtesting engine for strategy validation."""
import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class BacktestEngine:
    """Backtest trading strategies."""
    
    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.logger = logging.getLogger(__name__)
        self.trades = []
        self.equity_curve = []
    
    def run_backtest(self, strategy, data: List[Dict]) -> Dict:
        """Run backtest on historical data."""
        capital = self.initial_capital
        self.trades = []
        self.equity_curve = [capital]
        
        for i, bar in enumerate(data):
            signal = strategy.generate_signal(bar)
            
            if signal and signal.get('action') == 'buy':
                # Simulate trade
                price = bar.get('price', 0)
                amount = capital * 0.1  # 10% per trade
                cost = amount * (1 + 0.001)  # 0.1% fee
                
                if cost <= capital:
                    capital -= cost
                    self.trades.append({
                        'type': 'buy',
                        'price': price,
                        'amount': amount,
                        'timestamp': bar.get('timestamp')
                    })
            
            elif signal and signal.get('action') == 'sell' and self.trades:
                # Close trade
                last_trade = self.trades[-1]
                price = bar.get('price', 0)
                revenue = last_trade['amount'] * (price / last_trade['price']) * (1 - 0.001)
                capital += revenue
                
                last_trade['exit_price'] = price
                last_trade['profit'] = revenue - last_trade['amount']
            
            self.equity_curve.append(capital)
        
        return self._calculate_metrics(capital)
    
    def _calculate_metrics(self, final_capital: float) -> Dict:
        """Calculate backtest metrics."""
        total_return = (final_capital - self.initial_capital) / self.initial_capital * 100
        
        winning_trades = [t for t in self.trades if t.get('profit', 0) > 0]
        win_rate = len(winning_trades) / len(self.trades) * 100 if self.trades else 0
        
        # Calculate max drawdown
        peak = self.initial_capital
        max_dd = 0
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return {
            'total_return': total_return,
            'final_capital': final_capital,
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'max_drawdown': max_dd * 100,
            'sharpe_ratio': 0.0  # Simplified
        }
    
    def walk_forward_test(self, strategy, data: List[Dict], window_size: int = 100) -> List[Dict]:
        """Walk-forward testing."""
        results = []
        
        for i in range(0, len(data) - window_size, window_size // 2):
            window = data[i:i+window_size]
            result = self.run_backtest(strategy, window)
            results.append(result)
        
        return results
