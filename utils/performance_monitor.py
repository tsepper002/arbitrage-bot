"""
Performance Monitor - Real-time performance tracking and optimization
"""
import time
import psutil
import logging
from typing import Dict, List, Optional
from collections import deque
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    latency_ms: float
    trades_per_second: float
    profit_rate: float


class PerformanceMonitor:
    """Monitor and optimize bot performance in real-time"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics_history = deque(maxlen=window_size)
        self.trade_times = deque(maxlen=100)
        self.latency_samples = deque(maxlen=100)
        self.start_time = time.time()
        
    def record_trade(self, execution_time: float, profit: float):
        """Record a trade execution"""
        self.trade_times.append(time.time())
        
        metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            cpu_percent=psutil.cpu_percent(),
            memory_percent=psutil.virtual_memory().percent,
            latency_ms=execution_time * 1000,
            trades_per_second=self.calculate_tps(),
            profit_rate=profit
        )
        
        self.metrics_history.append(metrics)
        logger.debug(f"Trade recorded: {execution_time:.3f}s, profit: ${profit:.2f}")
        
    def record_latency(self, latency_ms: float):
        """Record network latency"""
        self.latency_samples.append(latency_ms)
        
    def calculate_tps(self) -> float:
        """Calculate current trades per second"""
        if len(self.trade_times) < 2:
            return 0.0
            
        now = time.time()
        recent = [t for t in self.trade_times if now - t <= 60]
        
        if len(recent) < 2:
            return 0.0
            
        duration = recent[-1] - recent[0]
        return len(recent) / duration if duration > 0 else 0.0
        
    def get_average_latency(self) -> float:
        """Get average latency in ms"""
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)
        
    def get_system_health(self) -> Dict:
        """Get current system health metrics"""
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        return {
            'cpu_percent': cpu,
            'memory_percent': memory.percent,
            'memory_available_mb': memory.available / (1024 * 1024),
            'uptime_hours': (time.time() - self.start_time) / 3600,
            'avg_latency_ms': self.get_average_latency(),
            'current_tps': self.calculate_tps()
        }
        
    def get_performance_summary(self) -> Dict:
        """Get performance summary statistics"""
        if not self.metrics_history:
            return {}
            
        cpu_values = [m.cpu_percent for m in self.metrics_history]
        memory_values = [m.memory_percent for m in self.metrics_history]
        latency_values = [m.latency_ms for m in self.metrics_history]
        profit_values = [m.profit_rate for m in self.metrics_history]
        
        return {
            'avg_cpu': sum(cpu_values) / len(cpu_values),
            'max_cpu': max(cpu_values),
            'avg_memory': sum(memory_values) / len(memory_values),
            'avg_latency_ms': sum(latency_values) / len(latency_values),
            'max_latency_ms': max(latency_values),
            'total_trades': len(self.metrics_history),
            'avg_profit': sum(profit_values) / len(profit_values) if profit_values else 0,
            'total_profit': sum(profit_values)
        }
        
    def check_performance_issues(self) -> List[str]:
        """Check for performance issues and return warnings"""
        warnings = []
        health = self.get_system_health()
        
        if health['cpu_percent'] > 80:
            warnings.append(f"High CPU usage: {health['cpu_percent']:.1f}%")
            
        if health['memory_percent'] > 85:
            warnings.append(f"High memory usage: {health['memory_percent']:.1f}%")
            
        if health['avg_latency_ms'] > 100:
            warnings.append(f"High latency: {health['avg_latency_ms']:.1f}ms")
            
        if health['current_tps'] < 0.1 and len(self.trade_times) > 10:
            warnings.append("Low trading activity")
            
        return warnings
        
    def suggest_optimizations(self) -> List[str]:
        """Suggest performance optimizations"""
        suggestions = []
        health = self.get_system_health()
        
        if health['cpu_percent'] > 70:
            suggestions.append("Consider reducing scan frequency")
            suggestions.append("Enable aggressive caching")
            
        if health['memory_percent'] > 75:
            suggestions.append("Clear old data from memory")
            suggestions.append("Reduce history buffer sizes")
            
        if health['avg_latency_ms'] > 50:
            suggestions.append("Optimize network connections")
            suggestions.append("Use closer exchange endpoints")
            
        return suggestions
        
    def get_report(self) -> str:
        """Generate performance report"""
        health = self.get_system_health()
        summary = self.get_performance_summary()
        warnings = self.check_performance_issues()
        suggestions = self.suggest_optimizations()
        
        report = ["=== Performance Report ==="]
        report.append(f"\nSystem Health:")
        report.append(f"  CPU: {health['cpu_percent']:.1f}%")
        report.append(f"  Memory: {health['memory_percent']:.1f}%")
        report.append(f"  Uptime: {health['uptime_hours']:.2f} hours")
        report.append(f"  Latency: {health['avg_latency_ms']:.2f}ms")
        report.append(f"  TPS: {health['current_tps']:.2f}")
        
        if summary:
            report.append(f"\nPerformance Summary:")
            report.append(f"  Total Trades: {summary['total_trades']}")
            report.append(f"  Avg Profit: ${summary['avg_profit']:.2f}")
            report.append(f"  Total Profit: ${summary['total_profit']:.2f}")
            report.append(f"  Avg Latency: {summary['avg_latency_ms']:.2f}ms")
            report.append(f"  Max Latency: {summary['max_latency_ms']:.2f}ms")
        
        if warnings:
            report.append(f"\n⚠ Warnings:")
            for w in warnings:
                report.append(f"  - {w}")
                
        if suggestions:
            report.append(f"\n💡 Suggestions:")
            for s in suggestions:
                report.append(f"  - {s}")
                
        return "\n".join(report)


# Global instance
_monitor = None


def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor
