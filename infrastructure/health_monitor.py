"""Health Monitor - System and exchange health checking"""
import logging
import time
import psutil
from typing import Dict, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self):
        self.start_time = datetime.now()
        self.health_checks = {}
        # Exchange API health tracking
        self._exchange_errors: Dict[str, list] = defaultdict(list)  # {exchange: [timestamps]}
        self._exchange_latencies: Dict[str, list] = defaultdict(list)  # {exchange: [latency_ms]}
        self._exchange_last_success: Dict[str, float] = {}  # {exchange: timestamp}
        self.ERROR_WINDOW_S = 300  # 5-minute window for error counting
        self.MAX_ERRORS_PER_WINDOW = 10  # Unhealthy if >10 errors in 5 min
        self.MAX_LATENCY_MS = 2000  # Unhealthy if avg latency > 2 seconds
        
    def register_component(self, name: str, check_func):
        """Register a component health check"""
        self.health_checks[name] = check_func
    
    def record_exchange_success(self, exchange: str, latency_ms: float):
        """Record a successful exchange API call"""
        now = time.time()
        self._exchange_last_success[exchange] = now
        self._exchange_latencies[exchange].append(latency_ms)
        # Keep only last 50 latency samples
        if len(self._exchange_latencies[exchange]) > 50:
            self._exchange_latencies[exchange] = self._exchange_latencies[exchange][-50:]
    
    def record_exchange_error(self, exchange: str, error: str):
        """Record a failed exchange API call"""
        now = time.time()
        self._exchange_errors[exchange].append(now)
        # Cleanup old errors outside window
        cutoff = now - self.ERROR_WINDOW_S
        self._exchange_errors[exchange] = [
            t for t in self._exchange_errors[exchange] if t > cutoff
        ]
    
    def is_exchange_healthy(self, exchange: str) -> bool:
        """Check if a specific exchange is healthy based on error rate and latency"""
        now = time.time()
        
        # Check error rate
        cutoff = now - self.ERROR_WINDOW_S
        recent_errors = [t for t in self._exchange_errors.get(exchange, []) if t > cutoff]
        if len(recent_errors) >= self.MAX_ERRORS_PER_WINDOW:
            logger.warning(f"🏥 {exchange} UNHEALTHY: {len(recent_errors)} errors in last {self.ERROR_WINDOW_S}s")
            return False
        
        # Check average latency
        latencies = self._exchange_latencies.get(exchange, [])
        if latencies and len(latencies) >= 5:
            avg_latency = sum(latencies[-10:]) / len(latencies[-10:])
            if avg_latency > self.MAX_LATENCY_MS:
                logger.warning(f"🏥 {exchange} UNHEALTHY: avg latency {avg_latency:.0f}ms > {self.MAX_LATENCY_MS}ms")
                return False
        
        return True
    
    def get_exchange_health(self) -> Dict[str, Dict]:
        """Get health status for all tracked exchanges"""
        now = time.time()
        result = {}
        for exchange in set(list(self._exchange_errors.keys()) + list(self._exchange_last_success.keys())):
            cutoff = now - self.ERROR_WINDOW_S
            recent_errors = [t for t in self._exchange_errors.get(exchange, []) if t > cutoff]
            latencies = self._exchange_latencies.get(exchange, [])
            avg_lat = sum(latencies[-10:]) / len(latencies[-10:]) if latencies else 0
            last_ok = self._exchange_last_success.get(exchange, 0)
            result[exchange] = {
                'healthy': self.is_exchange_healthy(exchange),
                'errors_5min': len(recent_errors),
                'avg_latency_ms': round(avg_lat, 1),
                'last_success_ago_s': round(now - last_ok, 1) if last_ok else None,
            }
        return result
        
    def check_system_health(self) -> Dict:
        """Check overall system health"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_mb': memory.available / (1024 * 1024),
            'disk_percent': disk.percent,
            'disk_free_gb': disk.free / (1024 * 1024 * 1024),
            'healthy': cpu_percent < 80 and memory.percent < 85 and disk.percent < 90
        }
        
    def check_components(self) -> Dict:
        """Check all registered components"""
        results = {}
        for name, check_func in self.health_checks.items():
            try:
                results[name] = check_func()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = {'healthy': False, 'error': str(e)}
        return results
        
    def get_uptime(self) -> Dict:
        """Get system uptime"""
        uptime = datetime.now() - self.start_time
        return {
            'uptime_seconds': uptime.total_seconds(),
            'uptime_hours': uptime.total_seconds() / 3600,
            'start_time': self.start_time.isoformat()
        }
        
    def get_full_status(self) -> Dict:
        """Get complete health status"""
        return {
            'system': self.check_system_health(),
            'exchanges': self.get_exchange_health(),
            'components': self.check_components(),
            'uptime': self.get_uptime(),
            'timestamp': datetime.now().isoformat()
        }
