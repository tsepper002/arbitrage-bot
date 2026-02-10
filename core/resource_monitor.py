#!/usr/bin/env python3
"""
Resource monitor for Windows 11 optimization (W4).
Monitors CPU and RAM usage, dynamically adjusts bot behavior.
"""
import asyncio
import logging
import psutil
from typing import Callable, Optional
import settings

logger = logging.getLogger("resource_monitor")


class ResourceMonitor:
    """
    Monitor system resources and adjust bot behavior accordingly.
    
    W4 OPTIMIZATION:
    - CPU > 60%: Reduce activity (increase scan interval, reduce depth)
    - CPU > 80%: Emergency mode (disable least profitable symbols)
    - CPU < 30%: Can increase activity (add symbols, decrease interval)
    - Memory > target: Warn and potentially reduce orderbook depth
    """
    
    def __init__(self, on_high_cpu: Optional[Callable] = None, on_critical_cpu: Optional[Callable] = None):
        """
        Initialize resource monitor.
        
        Args:
            on_high_cpu: Callback when CPU > high threshold
            on_critical_cpu: Callback when CPU > critical threshold
        """
        self.on_high_cpu = on_high_cpu
        self.on_critical_cpu = on_critical_cpu
        
        # Thresholds
        self.cpu_high_threshold = settings.CPU_HIGH_THRESHOLD
        self.cpu_critical_threshold = settings.CPU_CRITICAL_THRESHOLD
        self.cpu_low_threshold = settings.CPU_LOW_THRESHOLD
        self.memory_max_mb = settings.MEMORY_MAX_MB
        
        # State
        self.current_cpu_pct = 0.0
        self.current_memory_mb = 0.0
        self.cpu_state = "normal"  # normal, high, critical
        
        # Stats
        self.checks_performed = 0
        self.high_cpu_events = 0
        self.critical_cpu_events = 0
        
        logger.info(f"ResourceMonitor initialized:")
        logger.info(f"  CPU thresholds: low={self.cpu_low_threshold}%, high={self.cpu_high_threshold}%, critical={self.cpu_critical_threshold}%")
        logger.info(f"  Memory target: {self.memory_max_mb}MB")
    
    async def start_monitoring(self):
        """Start continuous resource monitoring."""
        logger.info("Starting resource monitoring loop...")
        
        while True:
            await asyncio.sleep(settings.CPU_CHECK_INTERVAL_SEC)
            await self.check_resources()
    
    async def check_resources(self):
        """Check current resource usage and take action if needed."""
        self.checks_performed += 1
        
        # Get current CPU usage (average over interval)
        self.current_cpu_pct = psutil.cpu_percent(interval=1)
        
        # Get current memory usage
        process = psutil.Process()
        self.current_memory_mb = process.memory_info().rss / (1024 * 1024)
        
        # Determine CPU state
        old_state = self.cpu_state
        
        if self.current_cpu_pct >= self.cpu_critical_threshold:
            self.cpu_state = "critical"
            if old_state != "critical":
                self.critical_cpu_events += 1
                logger.error(f"🔴 CRITICAL CPU: {self.current_cpu_pct:.1f}% - Emergency mode activated")
                if self.on_critical_cpu:
                    await self._safe_callback(self.on_critical_cpu, self.current_cpu_pct)
        
        elif self.current_cpu_pct >= self.cpu_high_threshold:
            self.cpu_state = "high"
            if old_state != "high":
                self.high_cpu_events += 1
                logger.warning(f"🟡 HIGH CPU: {self.current_cpu_pct:.1f}% - Reducing activity")
                if self.on_high_cpu:
                    await self._safe_callback(self.on_high_cpu, self.current_cpu_pct)
        
        else:
            self.cpu_state = "normal"
            if old_state in ["high", "critical"]:
                logger.info(f"✅ CPU normalized: {self.current_cpu_pct:.1f}%")
        
        # Check memory
        if self.current_memory_mb > self.memory_max_mb:
            logger.warning(f"⚠️  Memory usage high: {self.current_memory_mb:.1f}MB (target: {self.memory_max_mb}MB)")
        
        # Periodic status log (every 12 checks = 1 minute at 5s interval)
        if self.checks_performed % 12 == 0:
            self.log_status()
    
    async def _safe_callback(self, callback: Callable, *args):
        """Execute callback safely."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.exception(f"Error in resource monitor callback: {e}")
    
    def get_cpu_state(self) -> str:
        """Get current CPU state: normal, high, or critical."""
        return self.cpu_state
    
    def should_reduce_activity(self) -> bool:
        """Check if bot should reduce activity due to high CPU."""
        return self.cpu_state in ["high", "critical"]
    
    def should_emergency_mode(self) -> bool:
        """Check if bot should enter emergency mode due to critical CPU."""
        return self.cpu_state == "critical"
    
    def get_recommended_scan_interval(self, base_interval: float) -> float:
        """
        Get recommended scan interval based on CPU state.
        
        Args:
            base_interval: Normal scan interval
            
        Returns:
            Adjusted interval (higher when CPU is stressed)
        """
        if self.cpu_state == "critical":
            return base_interval * 4.0  # 4x slower in critical mode
        elif self.cpu_state == "high":
            return base_interval * 2.0  # 2x slower in high mode
        elif self.current_cpu_pct < self.cpu_low_threshold:
            return base_interval * 0.75  # 25% faster when CPU is idle
        else:
            return base_interval
    
    def get_recommended_depth(self, base_depth: int) -> int:
        """
        Get recommended orderbook depth based on CPU state.
        
        Args:
            base_depth: Normal depth (e.g., 20 levels)
            
        Returns:
            Adjusted depth (lower when CPU is stressed)
        """
        if self.cpu_state == "critical":
            return max(5, base_depth // 4)  # Use only 5 levels in critical mode
        elif self.cpu_state == "high":
            return max(10, base_depth // 2)  # Use 10 levels in high mode
        else:
            return base_depth
    
    def log_status(self):
        """Log current resource status."""
        logger.info(
            f"Resources: CPU={self.current_cpu_pct:.1f}% ({self.cpu_state}), "
            f"RAM={self.current_memory_mb:.1f}MB, "
            f"Checks={self.checks_performed}, "
            f"High CPU events={self.high_cpu_events}, "
            f"Critical events={self.critical_cpu_events}"
        )
    
    def get_statistics(self) -> dict:
        """Get resource monitoring statistics."""
        return {
            "current_cpu_pct": self.current_cpu_pct,
            "current_memory_mb": self.current_memory_mb,
            "cpu_state": self.cpu_state,
            "checks_performed": self.checks_performed,
            "high_cpu_events": self.high_cpu_events,
            "critical_cpu_events": self.critical_cpu_events,
            "thresholds": {
                "cpu_low": self.cpu_low_threshold,
                "cpu_high": self.cpu_high_threshold,
                "cpu_critical": self.cpu_critical_threshold,
                "memory_max_mb": self.memory_max_mb,
            }
        }


# Example usage
async def example_high_cpu_handler(cpu_pct: float):
    """Example handler for high CPU."""
    logger.info(f"Application responding to high CPU: {cpu_pct:.1f}%")
    # Here you would implement actions like:
    # - Increase scan intervals
    # - Reduce orderbook depth
    # - Pause low-priority strategies


async def example_critical_cpu_handler(cpu_pct: float):
    """Example handler for critical CPU."""
    logger.error(f"Application responding to CRITICAL CPU: {cpu_pct:.1f}%")
    # Here you would implement emergency actions like:
    # - Disable least profitable symbols
    # - Stop new trades
    # - Reduce to minimal monitoring
