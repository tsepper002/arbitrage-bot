"""Real-time Analytics - Live P&L and metrics tracking"""
import logging
from typing import Dict, List
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

class RealtimeAnalytics:
    def __init__(self):
        self.trades: List[Dict] = []
        self.pnl_history: List[tuple] = []  # [(timestamp, pnl), ...]
        self.metrics = defaultdict(float)
        self.start_time = datetime.now()
        
    def add_trade(self, trade: Dict):
        """Record a trade"""
        self.trades.append({
            'timestamp': datetime.now(),
            'symbol': trade.get('symbol'),
            'side': trade.get('side'),
            'amount': trade.get('amount'),
            'price': trade.get('price'),
            'fee': trade.get('fee', 0),
            'profit': trade.get('profit', 0)
        })
        self._update_metrics(trade)
        
    def _update_metrics(self, trade: Dict):
        """Update real-time metrics"""
        profit = trade.get('profit', 0)
        self.metrics['total_pnl'] += profit
        self.metrics['total_trades'] += 1
        
        if profit > 0:
            self.metrics['winning_trades'] += 1
            self.metrics['total_profit'] += profit
        else:
            self.metrics['losing_trades'] += 1
            self.metrics['total_loss'] += abs(profit)
            
        self.pnl_history.append((datetime.now(), self.metrics['total_pnl']))
        
    def get_current_stats(self) -> Dict:
        """Get current statistics"""
        total = self.metrics['total_trades']
        winning = self.metrics['winning_trades']
        
        win_rate = (winning / total * 100) if total > 0 else 0
        avg_profit = self.metrics['total_profit'] / winning if winning > 0 else 0
        avg_loss = self.metrics['total_loss'] / self.metrics['losing_trades'] if self.metrics['losing_trades'] > 0 else 0
        
        uptime = (datetime.now() - self.start_time).total_seconds() / 3600
        
        return {
            'total_pnl': self.metrics['total_pnl'],
            'total_trades': total,
            'winning_trades': winning,
            'losing_trades': self.metrics['losing_trades'],
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'profit_factor': abs(avg_profit / avg_loss) if avg_loss != 0 else 0,
            'uptime_hours': uptime,
            'trades_per_hour': total / uptime if uptime > 0 else 0
        }
        
    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get most recent trades"""
        return self.trades[-limit:]
        
    def reset(self):
        """Reset all statistics"""
        self.trades.clear()
        self.pnl_history.clear()
        self.metrics.clear()
        self.start_time = datetime.now()
