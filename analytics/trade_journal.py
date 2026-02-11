"""Trade Journal - Complete trade history and export"""
import logging
import json
import csv
from typing import Dict, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class TradeJournal:
    def __init__(self, journal_path: str = "./trade_journal.json"):
        self.journal_path = Path(journal_path)
        self.trades: List[Dict] = []
        self._load_journal()
        
    def _load_journal(self):
        """Load existing journal"""
        if self.journal_path.exists():
            try:
                with open(self.journal_path, 'r') as f:
                    self.trades = json.load(f)
                logger.info(f"Loaded {len(self.trades)} trades from journal")
            except Exception as e:
                logger.error(f"Failed to load journal: {e}")
                self.trades = []
                
    def record_trade(self, trade: Dict):
        """Record a new trade"""
        trade_record = {
            'id': len(self.trades) + 1,
            'timestamp': datetime.now().isoformat(),
            'symbol': trade.get('symbol'),
            'side': trade.get('side'),
            'amount': trade.get('amount'),
            'price': trade.get('price'),
            'fee': trade.get('fee', 0),
            'profit': trade.get('profit', 0),
            'strategy': trade.get('strategy', 'unknown'),
            'exchange': trade.get('exchange'),
            'notes': trade.get('notes', '')
        }
        
        self.trades.append(trade_record)
        self._save_journal()
        
    def _save_journal(self):
        """Save journal to file"""
        try:
            with open(self.journal_path, 'w') as f:
                json.dump(self.trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save journal: {e}")
            
    def export_to_csv(self, csv_path: str = "./trades.csv"):
        """Export trades to CSV"""
        if not self.trades:
            logger.warning("No trades to export")
            return
            
        try:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.trades[0].keys())
                writer.writeheader()
                writer.writerows(self.trades)
            logger.info(f"Exported {len(self.trades)} trades to {csv_path}")
        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            
    def get_trades_by_date(self, start_date: str, end_date: str) -> List[Dict]:
        """Get trades within date range"""
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        filtered = [
            t for t in self.trades
            if start <= datetime.fromisoformat(t['timestamp']) <= end
        ]
        return filtered
        
    def get_trades_by_symbol(self, symbol: str) -> List[Dict]:
        """Get all trades for a symbol"""
        return [t for t in self.trades if t['symbol'] == symbol]
        
    def get_profit_by_strategy(self) -> Dict[str, float]:
        """Calculate profit per strategy"""
        profit_by_strategy = {}
        for trade in self.trades:
            strategy = trade.get('strategy', 'unknown')
            profit = trade.get('profit', 0)
            profit_by_strategy[strategy] = profit_by_strategy.get(strategy, 0) + profit
        return profit_by_strategy
        
    def get_summary(self) -> Dict:
        """Get journal summary"""
        if not self.trades:
            return {'total_trades': 0}
            
        total_profit = sum(t.get('profit', 0) for t in self.trades)
        total_fees = sum(t.get('fee', 0) for t in self.trades)
        
        return {
            'total_trades': len(self.trades),
            'total_profit': total_profit,
            'total_fees': total_fees,
            'net_profit': total_profit - total_fees,
            'first_trade': self.trades[0]['timestamp'],
            'last_trade': self.trades[-1]['timestamp']
        }
