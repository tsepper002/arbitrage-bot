#!/usr/bin/env python3
"""
Watchdog - System health monitoring and auto-restart functionality.
Monitors WebSocket connections, system resources, and main loop health.
"""
import asyncio
import logging
import time
import signal
import sys
import os
from typing import Dict, Optional, Callable
import psutil

logger = logging.getLogger("watchdog")


class Watchdog:
    """
    Health monitoring and auto-restart system.
    Watches for stale connections, frozen loops, and system resource issues.
    """
    
    def __init__(self, check_interval: float = 30.0):
        """
        Initialize watchdog.
        
        Args:
            check_interval: Health check interval in seconds
        """
        self.check_interval = check_interval
        self.is_running = False
        self._stop_event = asyncio.Event()
        
        # Health tracking
        self.last_activity: Dict[str, float] = {}
        self.stale_threshold = 60.0  # Alert if no activity for 60s
        
        # System resource tracking
        self.process = psutil.Process()
        self.cpu_threshold = 80.0  # Alert if CPU > 80%
        self.memory_threshold = 80.0  # Alert if memory > 80%
        
        # Callbacks
        self.on_stale_connection: Optional[Callable] = None
        self.on_resource_warning: Optional[Callable] = None
        self.on_shutdown_request: Optional[Callable] = None
        
        # Graceful shutdown handling
        self._setup_signal_handlers()
        
        logger.info(f"Watchdog initialized: check_interval={check_interval}s")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            if self.on_shutdown_request:
                # Call shutdown callback
                self.on_shutdown_request()
            else:
                # Default: just stop the watchdog
                self.stop()
                sys.exit(0)
        
        # Handle SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Windows-specific: handle Ctrl+Break
        if sys.platform == 'win32':
            signal.signal(signal.SIGBREAK, signal_handler)
    
    def record_activity(self, component: str):
        """
        Record activity for a component.
        
        Args:
            component: Component name (e.g., "Bybit_WS", "main_loop")
        """
        self.last_activity[component] = time.time()
    
    def check_stale_connections(self) -> Dict[str, float]:
        """
        Check for stale connections.
        
        Returns:
            Dictionary of stale components and their time since last activity
        """
        current_time = time.time()
        stale_components = {}
        
        for component, last_time in self.last_activity.items():
            time_since_activity = current_time - last_time
            if time_since_activity > self.stale_threshold:
                stale_components[component] = time_since_activity
        
        return stale_components
    
    def check_system_resources(self) -> Dict[str, any]:
        """
        Check system resource usage.
        
        Returns:
            Dictionary with resource usage information
        """
        try:
            cpu_percent = self.process.cpu_percent(interval=0.1)
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            # System-wide stats
            system_cpu = psutil.cpu_percent(interval=0.1)
            system_memory = psutil.virtual_memory().percent
            
            return {
                'process_cpu_percent': cpu_percent,
                'process_memory_mb': memory_info.rss / 1024 / 1024,
                'process_memory_percent': memory_percent,
                'system_cpu_percent': system_cpu,
                'system_memory_percent': system_memory,
                'cpu_warning': cpu_percent > self.cpu_threshold,
                'memory_warning': memory_percent > self.memory_threshold,
            }
        except Exception as e:
            logger.error(f"Failed to check system resources: {e}")
            return {}
    
    async def health_check_loop(self):
        """Main health check loop."""
        self.is_running = True
        logger.info("Watchdog health check loop started")
        
        while not self._stop_event.is_set():
            try:
                # Check for stale connections
                stale = self.check_stale_connections()
                if stale:
                    logger.warning(f"⚠️  Stale components detected: {stale}")
                    if self.on_stale_connection:
                        self.on_stale_connection(stale)
                
                # Check system resources
                resources = self.check_system_resources()
                if resources:
                    if resources.get('cpu_warning') or resources.get('memory_warning'):
                        logger.warning(
                            f"⚠️  High resource usage: "
                            f"CPU={resources['process_cpu_percent']:.1f}% "
                            f"Memory={resources['process_memory_mb']:.1f}MB ({resources['process_memory_percent']:.1f}%)"
                        )
                        if self.on_resource_warning:
                            self.on_resource_warning(resources)
                    else:
                        logger.debug(
                            f"Resources: CPU={resources['process_cpu_percent']:.1f}% "
                            f"Memory={resources['process_memory_mb']:.1f}MB"
                        )
                
                # Wait for next check
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.check_interval
                )
                
            except asyncio.TimeoutError:
                # Expected - time for next check
                pass
            except Exception as e:
                logger.exception(f"Error in watchdog health check: {e}")
                await asyncio.sleep(self.check_interval)
        
        self.is_running = False
        logger.info("Watchdog health check loop stopped")
    
    def start(self) -> asyncio.Task:
        """
        Start the watchdog.
        
        Returns:
            The asyncio task running the health check loop
        """
        return asyncio.create_task(self.health_check_loop())
    
    def stop(self):
        """Stop the watchdog."""
        logger.info("Stopping watchdog...")
        self._stop_event.set()
    
    def get_status(self) -> Dict[str, any]:
        """Get current watchdog status."""
        stale = self.check_stale_connections()
        resources = self.check_system_resources()
        
        return {
            'is_running': self.is_running,
            'monitored_components': len(self.last_activity),
            'stale_components': stale,
            'system_resources': resources,
        }
    
    def print_status(self):
        """Print watchdog status to console."""
        status = self.get_status()
        
        print("\n" + "="*60)
        print("  Watchdog Status")
        print("="*60)
        print(f"  Running: {'✅ Yes' if status['is_running'] else '❌ No'}")
        print(f"  Monitored Components: {status['monitored_components']}")
        
        if status['stale_components']:
            print(f"  ⚠️  Stale Components: {len(status['stale_components'])}")
            for comp, time_stale in status['stale_components'].items():
                print(f"    - {comp}: {time_stale:.0f}s since last activity")
        else:
            print(f"  ✅ All components healthy")
        
        resources = status.get('system_resources', {})
        if resources:
            print(f"\n  System Resources:")
            print(f"    Process CPU: {resources.get('process_cpu_percent', 0):.1f}%")
            print(f"    Process Memory: {resources.get('process_memory_mb', 0):.1f} MB ({resources.get('process_memory_percent', 0):.1f}%)")
            print(f"    System CPU: {resources.get('system_cpu_percent', 0):.1f}%")
            print(f"    System Memory: {resources.get('system_memory_percent', 0):.1f}%")
            
            if resources.get('cpu_warning') or resources.get('memory_warning'):
                print(f"  ⚠️  Resource warnings active")
        
        print("="*60 + "\n")


class WebSocketWatchdog:
    """
    Specialized watchdog for WebSocket connections.
    Monitors connection health and triggers reconnection.
    """
    
    def __init__(self, ws_clients: Dict[str, any], watchdog: Watchdog):
        """
        Initialize WebSocket watchdog.
        
        Args:
            ws_clients: Dictionary of exchange_name -> WebSocket client
            watchdog: Main watchdog instance
        """
        self.ws_clients = ws_clients
        self.watchdog = watchdog
        
        logger.info(f"WebSocketWatchdog initialized for {len(ws_clients)} exchanges")
    
    async def monitor_connections(self):
        """Monitor WebSocket connection health."""
        while True:
            for exchange, client in self.ws_clients.items():
                try:
                    # Check if client has health status method
                    if hasattr(client, 'get_health_status'):
                        health = client.get_health_status()
                        
                        if not health.get('is_healthy', False):
                            logger.warning(f"⚠️  {exchange} connection unhealthy: {health}")
                            # Record as stale in main watchdog
                            # Reconnection is handled by the WS client itself
                        else:
                            # Record healthy activity
                            self.watchdog.record_activity(f"{exchange}_WS")
                
                except Exception as e:
                    logger.error(f"Error checking {exchange} health: {e}")
            
            await asyncio.sleep(30)  # Check every 30 seconds
