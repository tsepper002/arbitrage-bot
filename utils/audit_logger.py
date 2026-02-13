"""
Audit Logger - Comprehensive logging system for all bot operations
Tracks trades, errors, performance metrics, and system events
"""
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import sqlite3
from contextlib import contextmanager

class AuditLogger:
    """Audit logger for tracking all bot operations"""
    
    def __init__(self, db_path: str = "data/audit.db"):
        self.db_path = db_path
        self.setup_database()
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger('AuditLogger')
        logger.setLevel(logging.DEBUG)
        
        # File handler
        fh = logging.FileHandler('logs/audit.log')
        fh.setLevel(logging.DEBUG)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    @contextmanager
    def get_db(self):
        """Database connection context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def setup_database(self):
        """Initialize audit database"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with self.get_db() as conn:
            cursor = conn.cursor()
            
            # Trades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL,
                    order_id TEXT,
                    strategy TEXT,
                    pnl REAL,
                    metadata TEXT
                )
            ''')
            
            # Errors table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    stack_trace TEXT,
                    context TEXT
                )
            ''')
            
            # Performance table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metadata TEXT
                )
            ''')
            
            # System events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    data TEXT
                )
            ''')
            
            conn.commit()
    
    def log_trade(self, exchange: str, symbol: str, side: str, 
                  price: float, amount: float, **kwargs):
        """Log a trade execution"""
        with self.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades 
                (timestamp, exchange, symbol, side, price, amount, fee, 
                 order_id, strategy, pnl, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().timestamp(),
                exchange,
                symbol,
                side,
                price,
                amount,
                kwargs.get('fee'),
                kwargs.get('order_id'),
                kwargs.get('strategy'),
                kwargs.get('pnl'),
                json.dumps(kwargs.get('metadata', {}))
            ))
            conn.commit()
        
        self.logger.info(
            f"Trade: {side} {amount} {symbol} @ {price} on {exchange}"
        )
    
    def log_error(self, error_type: str, error_message: str, 
                  stack_trace: Optional[str] = None, context: Optional[Dict] = None):
        """Log an error"""
        with self.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO errors 
                (timestamp, error_type, error_message, stack_trace, context)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                datetime.now().timestamp(),
                error_type,
                error_message,
                stack_trace,
                json.dumps(context or {})
            ))
            conn.commit()
        
        self.logger.error(f"{error_type}: {error_message}")
    
    def log_performance(self, metric_name: str, metric_value: float, 
                       metadata: Optional[Dict] = None):
        """Log performance metric"""
        with self.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO performance 
                (timestamp, metric_name, metric_value, metadata)
                VALUES (?, ?, ?, ?)
            ''', (
                datetime.now().timestamp(),
                metric_name,
                metric_value,
                json.dumps(metadata or {})
            ))
            conn.commit()
    
    def log_system_event(self, event_type: str, description: str, 
                        data: Optional[Dict] = None):
        """Log system event"""
        with self.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_events 
                (timestamp, event_type, description, data)
                VALUES (?, ?, ?, ?)
            ''', (
                datetime.now().timestamp(),
                event_type,
                description,
                json.dumps(data or {})
            ))
            conn.commit()
        
        self.logger.info(f"Event: {event_type} - {description}")
    
    def get_trades(self, limit: int = 100, exchange: Optional[str] = None) -> list:
        """Retrieve recent trades"""
        with self.get_db() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM trades"
            params = []
            
            if exchange:
                query += " WHERE exchange = ?"
                params.append(exchange)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_daily_stats(self) -> Dict[str, Any]:
        """Get daily trading statistics"""
        with self.get_db() as conn:
            cursor = conn.cursor()
            
            today_start = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            ).timestamp()
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as trade_count,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    SUM(fee) as total_fees
                FROM trades
                WHERE timestamp >= ?
            ''', (today_start,))
            
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    def cleanup_old_data(self, days: int = 90):
        """Remove data older than specified days"""
        cutoff = datetime.now().timestamp() - (days * 24 * 3600)
        
        with self.get_db() as conn:
            cursor = conn.cursor()
            
            for table in ['trades', 'errors', 'performance', 'system_events']:
                cursor.execute(f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,))
            
            conn.commit()
        
        self.logger.info(f"Cleaned up data older than {days} days")

# Global audit logger instance
_audit_logger = None

def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
