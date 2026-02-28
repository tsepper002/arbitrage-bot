"""
Health Monitor - Proactive system health monitoring
Monitors all components and provides real-time health status.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheck:
    """Represents a health check for a component."""
    
    def __init__(
        self,
        component: str,
        check_func: Callable,
        interval_seconds: int = 60,
        timeout_seconds: int = 5
    ):
        """
        Initialize health check.
        
        Args:
            component: Component name
            check_func: Async function that returns True if healthy
            interval_seconds: Time between checks
            timeout_seconds: Timeout for check execution
        """
        self.component = component
        self.check_func = check_func
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        
        self.last_check_time: Optional[float] = None
        self.last_status: HealthStatus = HealthStatus.UNKNOWN
        self.last_error: Optional[str] = None
        self.consecutive_failures = 0
        self.check_count = 0
        self.failure_count = 0


class HealthMonitor:
    """
    Monitors system health and component status.
    
    Features:
    - Per-component health checks
    - Automatic periodic checking
    - Status dashboard
    - Alert on degradation
    - Configurable thresholds
    """
    
    def __init__(self, check_interval: int = 30):
        """
        Initialize health monitor.
        
        Args:
            check_interval: Default interval between checks (seconds)
        """
        self.check_interval = check_interval
        self.checks: Dict[str, HealthCheck] = {}
        self.monitoring_task: Optional[asyncio.Task] = None
        self.running = False
        self.lock = asyncio.Lock()
        
        logger.info(f"HealthMonitor initialized with interval={check_interval}s")
    
    async def register_component(
        self,
        component: str,
        check_func: Callable,
        interval_seconds: Optional[int] = None,
        timeout_seconds: int = 5
    ):
        """
        Register a component for health monitoring.
        
        Args:
            component: Component name
            check_func: Async function that returns True if healthy
            interval_seconds: Check interval (uses default if None)
            timeout_seconds: Timeout for check execution
        """
        async with self.lock:
            interval = interval_seconds or self.check_interval
            
            health_check = HealthCheck(
                component=component,
                check_func=check_func,
                interval_seconds=interval,
                timeout_seconds=timeout_seconds
            )
            
            self.checks[component] = health_check
            logger.info(f"Registered health check for component: {component}")
    
    async def _execute_check(self, check: HealthCheck) -> HealthStatus:
        """
        Execute a single health check.
        
        Args:
            check: HealthCheck to execute
        
        Returns:
            HealthStatus
        """
        try:
            # Execute check with timeout
            result = await asyncio.wait_for(
                check.check_func(),
                timeout=check.timeout_seconds
            )
            
            check.check_count += 1
            check.last_check_time = time.time()
            
            if result:
                check.consecutive_failures = 0
                check.last_status = HealthStatus.HEALTHY
                check.last_error = None
                return HealthStatus.HEALTHY
            else:
                check.consecutive_failures += 1
                check.failure_count += 1
                check.last_status = HealthStatus.UNHEALTHY
                check.last_error = "Check returned False"
                
                logger.warning(
                    f"Health check failed for {check.component}: "
                    f"consecutive failures={check.consecutive_failures}"
                )
                return HealthStatus.UNHEALTHY
        
        except asyncio.TimeoutError:
            check.consecutive_failures += 1
            check.failure_count += 1
            check.last_status = HealthStatus.UNHEALTHY
            check.last_error = f"Timeout after {check.timeout_seconds}s"
            
            logger.error(f"Health check timeout for {check.component}")
            return HealthStatus.UNHEALTHY
        
        except Exception as e:
            check.consecutive_failures += 1
            check.failure_count += 1
            check.last_status = HealthStatus.UNHEALTHY
            check.last_error = str(e)
            
            logger.error(f"Health check error for {check.component}: {e}")
            return HealthStatus.UNHEALTHY
    
    async def check_component(self, component: str) -> HealthStatus:
        """
        Check health of specific component.
        
        Args:
            component: Component name
        
        Returns:
            HealthStatus
        """
        async with self.lock:
            if component not in self.checks:
                logger.warning(f"No health check registered for component: {component}")
                return HealthStatus.UNKNOWN
            
            check = self.checks[component]
            return await self._execute_check(check)
    
    async def check_all(self) -> Dict[str, HealthStatus]:
        """
        Check health of all components.
        
        Returns:
            Dictionary mapping component names to health status
        """
        results = {}
        
        async with self.lock:
            for component, check in self.checks.items():
                results[component] = await self._execute_check(check)
        
        return results
    
    async def get_overall_status(self) -> HealthStatus:
        """
        Get overall system health status.
        
        Returns:
            HEALTHY if all healthy, DEGRADED if some degraded, UNHEALTHY if any unhealthy
        """
        async with self.lock:
            return await self._get_overall_status_unlocked()

    async def _get_overall_status_unlocked(self) -> HealthStatus:
        """Internal: get status without acquiring lock (caller must hold lock)."""
        if not self.checks:
            return HealthStatus.UNKNOWN
        
        statuses = [check.last_status for check in self.checks.values()]
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        else:
            return HealthStatus.DEGRADED
    
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        logger.info("Health monitoring loop started")
        
        while self.running:
            try:
                # Check each component if it's time
                current_time = time.time()
                
                async with self.lock:
                    for component, check in self.checks.items():
                        # Check if it's time for this component's check
                        if (check.last_check_time is None or
                            current_time - check.last_check_time >= check.interval_seconds):
                            
                            await self._execute_check(check)
                
                # Sleep for a short interval
                await asyncio.sleep(5)
            
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
        
        logger.info("Health monitoring loop stopped")
    
    async def start(self):
        """Start health monitoring."""
        if self.running:
            logger.warning("Health monitoring already running")
            return
        
        self.running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health monitoring started")
    
    async def stop(self):
        """Stop health monitoring."""
        if not self.running:
            return
        
        self.running = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health monitoring stopped")
    
    async def get_status_dashboard(self) -> dict:
        """
        Get comprehensive health status dashboard.
        
        Returns:
            Dashboard with all component statuses and statistics
        """
        async with self.lock:
            overall_status = await self._get_overall_status_unlocked()
            
            components = {}
            for component, check in self.checks.items():
                components[component] = {
                    'status': check.last_status.value,
                    'last_check': (
                        datetime.fromtimestamp(check.last_check_time).isoformat()
                        if check.last_check_time else None
                    ),
                    'last_error': check.last_error,
                    'consecutive_failures': check.consecutive_failures,
                    'total_checks': check.check_count,
                    'total_failures': check.failure_count,
                    'success_rate': (
                        (check.check_count - check.failure_count) / check.check_count * 100
                        if check.check_count > 0 else 0
                    )
                }
            
            return {
                'overall_status': overall_status.value,
                'timestamp': datetime.now().isoformat(),
                'components': components,
                'total_components': len(self.checks),
                'healthy_components': sum(
                    1 for c in self.checks.values()
                    if c.last_status == HealthStatus.HEALTHY
                ),
                'monitoring_active': self.running
            }
    
    async def get_unhealthy_components(self) -> List[str]:
        """
        Get list of unhealthy components.
        
        Returns:
            List of component names that are unhealthy
        """
        async with self.lock:
            return [
                component for component, check in self.checks.items()
                if check.last_status == HealthStatus.UNHEALTHY
            ]
    
    async def get_alerts(self, threshold_failures: int = 3) -> List[dict]:
        """
        Get components that need attention.
        
        Args:
            threshold_failures: Number of consecutive failures to trigger alert
        
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        async with self.lock:
            for component, check in self.checks.items():
                if check.consecutive_failures >= threshold_failures:
                    alerts.append({
                        'component': component,
                        'status': check.last_status.value,
                        'consecutive_failures': check.consecutive_failures,
                        'last_error': check.last_error,
                        'last_check': (
                            datetime.fromtimestamp(check.last_check_time).isoformat()
                            if check.last_check_time else None
                        )
                    })
        
        return alerts


# Global instance
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor(check_interval: int = 30) -> HealthMonitor:
    """
    Get global health monitor instance.
    
    Args:
        check_interval: Default check interval in seconds
    
    Returns:
        HealthMonitor instance
    """
    global _health_monitor
    
    if _health_monitor is None:
        _health_monitor = HealthMonitor(check_interval=check_interval)
    
    return _health_monitor


# Usage example
"""
from core.health_monitor import get_health_monitor, HealthStatus

health_monitor = get_health_monitor()

# Register components
async def check_database():
    try:
        # Check database connection
        await db.ping()
        return True
    except:
        return False

async def check_exchange_api():
    try:
        # Check exchange API
        await exchange.get_ticker('BTC/USDT')
        return True
    except:
        return False

await health_monitor.register_component('database', check_database, interval_seconds=60)
await health_monitor.register_component('exchange_api', check_exchange_api, interval_seconds=30)

# Start monitoring
await health_monitor.start()

# Check specific component
status = await health_monitor.check_component('database')
print(f"Database status: {status}")

# Get overall status
overall = await health_monitor.get_overall_status()
print(f"Overall status: {overall}")

# Get dashboard
dashboard = await health_monitor.get_status_dashboard()
print(f"Healthy components: {dashboard['healthy_components']}/{dashboard['total_components']}")

# Get alerts
alerts = await health_monitor.get_alerts(threshold_failures=3)
for alert in alerts:
    print(f"Alert: {alert['component']} has {alert['consecutive_failures']} consecutive failures")

# Get unhealthy components
unhealthy = await health_monitor.get_unhealthy_components()
print(f"Unhealthy components: {unhealthy}")

# Stop monitoring when done
await health_monitor.stop()
"""
