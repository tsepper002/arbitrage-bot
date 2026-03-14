"""
Health Checker - Monitors bot health and system status
Checks exchange connectivity, balance sufficiency, and system resources
"""
import psutil
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio

class HealthChecker:
    """Comprehensive health monitoring for the arbitrage bot"""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.health_history: List[Dict] = []
        self.max_history = 1000
        self.alerts: List[Dict] = []
        
        # Thresholds
        self.cpu_threshold = 80.0  # %
        self.memory_threshold = 85.0  # %
        self.disk_threshold = 90.0  # %
        self.latency_threshold = 1000  # ms
        
    def check_system_resources(self) -> Dict[str, Any]:
        """Check CPU, memory, and disk usage"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'cpu': {
                'percent': cpu_percent,
                'healthy': cpu_percent < self.cpu_threshold
            },
            'memory': {
                'percent': memory.percent,
                'available_mb': memory.available / (1024**2),
                'healthy': memory.percent < self.memory_threshold
            },
            'disk': {
                'percent': disk.percent,
                'free_gb': disk.free / (1024**3),
                'healthy': disk.percent < self.disk_threshold
            }
        }
        
        # Generate alerts
        if cpu_percent >= self.cpu_threshold:
            self._add_alert('high_cpu', f'CPU usage at {cpu_percent}%')
        
        if memory.percent >= self.memory_threshold:
            self._add_alert('high_memory', f'Memory usage at {memory.percent}%')
        
        if disk.percent >= self.disk_threshold:
            self._add_alert('high_disk', f'Disk usage at {disk.percent}%')
        
        return status
    
    def check_exchange_connectivity(self, exchanges: Dict) -> Dict[str, Any]:
        """Check if exchanges are reachable"""
        connectivity = {}
        
        for exchange_name, exchange_obj in exchanges.items():
            try:
                start_time = time.time()
                # Attempt to fetch ticker (lightweight API call)
                exchange_obj.fetch_ticker('BTC/USDT')
                latency = (time.time() - start_time) * 1000  # ms
                
                connectivity[exchange_name] = {
                    'status': 'online',
                    'latency_ms': latency,
                    'healthy': latency < self.latency_threshold
                }
                
                if latency >= self.latency_threshold:
                    self._add_alert(
                        'high_latency',
                        f'{exchange_name} latency: {latency:.0f}ms'
                    )
                    
            except Exception as e:
                connectivity[exchange_name] = {
                    'status': 'offline',
                    'error': str(e),
                    'healthy': False
                }
                self._add_alert('exchange_offline', f'{exchange_name}: {str(e)}')
        
        return connectivity
    
    def check_balances(self, exchanges: Dict, 
                      min_balance_usd: float = 10.0) -> Dict[str, Any]:
        """Check if balances are sufficient for trading"""
        balances = {}
        
        for exchange_name, exchange_obj in exchanges.items():
            try:
                balance = exchange_obj.fetch_balance()
                total_usd = balance.get('total', {}).get('USDT', 0)
                
                balances[exchange_name] = {
                    'usd': total_usd,
                    'healthy': total_usd >= min_balance_usd
                }
                
                if total_usd < min_balance_usd:
                    self._add_alert(
                        'low_balance',
                        f'{exchange_name}: ${total_usd:.2f} (min ${min_balance_usd})'
                    )
                    
            except Exception as e:
                balances[exchange_name] = {
                    'error': str(e),
                    'healthy': False
                }
        
        return balances
    
    def check_trade_activity(self, audit_logger) -> Dict[str, Any]:
        """Check recent trading activity"""
        try:
            # Get trades from last hour
            recent_trades = audit_logger.get_trades(limit=100)
            
            one_hour_ago = datetime.now().timestamp() - 3600
            trades_last_hour = [
                t for t in recent_trades 
                if t.get('timestamp', 0) > one_hour_ago
            ]
            
            activity = {
                'trades_last_hour': len(trades_last_hour),
                'total_recent_trades': len(recent_trades),
                'healthy': True  # Can add more logic here
            }
            
            # Alert if no trades in last hour (might be intentional)
            if len(trades_last_hour) == 0:
                self._add_alert(
                    'no_trades',
                    'No trades executed in the last hour',
                    severity='info'
                )
            
            return activity
            
        except Exception as e:
            return {
                'error': str(e),
                'healthy': False
            }
    
    def check_errors(self, audit_logger) -> Dict[str, Any]:
        """Check for recent errors"""
        try:
            with audit_logger.get_db() as conn:
                cursor = conn.cursor()
                
                # Count errors in last hour
                one_hour_ago = datetime.now().timestamp() - 3600
                cursor.execute('''
                    SELECT COUNT(*) as error_count,
                           error_type
                    FROM errors
                    WHERE timestamp > ?
                    GROUP BY error_type
                ''', (one_hour_ago,))
                
                error_summary = {}
                total_errors = 0
                
                for row in cursor.fetchall():
                    count = row[0]
                    error_type = row[1]
                    error_summary[error_type] = count
                    total_errors += count
                
                status = {
                    'total_errors_last_hour': total_errors,
                    'by_type': error_summary,
                    'healthy': total_errors < 10  # Threshold
                }
                
                if total_errors >= 10:
                    self._add_alert(
                        'high_error_rate',
                        f'{total_errors} errors in last hour'
                    )
                
                return status
                
        except Exception as e:
            return {
                'error': str(e),
                'healthy': False
            }
    
    def perform_full_health_check(self, exchanges: Dict = None, 
                                 audit_logger=None) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'system': self.check_system_resources()
        }
        
        if exchanges:
            health_status['exchanges'] = self.check_exchange_connectivity(exchanges)
            health_status['balances'] = self.check_balances(exchanges)
        
        if audit_logger:
            health_status['trade_activity'] = self.check_trade_activity(audit_logger)
            health_status['errors'] = self.check_errors(audit_logger)
        
        # Overall health
        all_checks = []
        for category, data in health_status.items():
            if isinstance(data, dict) and 'healthy' in data:
                all_checks.append(data['healthy'])
            elif isinstance(data, dict):
                for item in data.values():
                    if isinstance(item, dict) and 'healthy' in item:
                        all_checks.append(item['healthy'])
        
        health_status['overall_healthy'] = all(all_checks) if all_checks else None
        health_status['health_score'] = (
            sum(all_checks) / len(all_checks) * 100 
            if all_checks else None
        )
        
        # Store in history
        self._store_health_check(health_status)
        
        return health_status
    
    def _add_alert(self, alert_type: str, message: str, severity: str = 'warning'):
        """Add an alert to the alerts list"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'message': message,
            'severity': severity
        }
        self.alerts.append(alert)
        
        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    def _store_health_check(self, health_status: Dict):
        """Store health check in history"""
        self.health_history.append(health_status)
        
        # Keep only last N checks
        if len(self.health_history) > self.max_history:
            self.health_history = self.health_history[-self.max_history:]
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Get recent alerts"""
        return self.alerts[-limit:]
    
    def get_health_history(self, hours: int = 24) -> List[Dict]:
        """Get health check history for specified hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        return [
            check for check in self.health_history
            if datetime.fromisoformat(check['timestamp']) > cutoff
        ]
    
    def clear_alerts(self):
        """Clear all alerts"""
        self.alerts = []
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current health status"""
        if not self.health_history:
            return {'message': 'No health checks performed yet'}
        
        latest = self.health_history[-1]
        
        return {
            'last_check': latest['timestamp'],
            'overall_healthy': latest.get('overall_healthy'),
            'health_score': latest.get('health_score'),
            'active_alerts': len(self.alerts),
            'recent_checks': len(self.health_history)
        }

# Global health checker instance
_health_checker = None

def get_health_checker() -> HealthChecker:
    """Get or create global health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
