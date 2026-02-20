"""Health Monitor - System health checking"""
import logging
import psutil
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self):
        self.start_time = datetime.now()
        self.health_checks = {}
        
    def register_component(self, name: str, check_func):
        """Register a component health check"""
        self.health_checks[name] = check_func
        
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
            'components': self.check_components(),
            'uptime': self.get_uptime(),
            'timestamp': datetime.now().isoformat()
        }
