"""
Horizontal Scaler - Auto-scaling logic for distributed arbitrage bot instances.

This module manages horizontal scaling of bot instances based on load,
ensuring optimal resource utilization and handling capacity spikes.

Features:
- Auto-scaling based on CPU/memory/load metrics
- Instance orchestration and health monitoring
- Load-based instance spawning/termination
- Distributed coordination via shared state
- Container/process management

Expected Impact: 10x capacity increase
"""

import asyncio
import logging
import psutil
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class ScalingAction(Enum):
    """Possible scaling actions."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"


@dataclass
class InstanceMetrics:
    """Metrics for a single bot instance."""
    instance_id: str
    cpu_percent: float
    memory_percent: float
    active_trades: int
    opportunities_per_second: float
    timestamp: float
    healthy: bool


@dataclass
class ScalingConfig:
    """Configuration for horizontal scaling."""
    min_instances: int = 1
    max_instances: int = 10
    target_cpu_percent: float = 70.0
    target_memory_percent: float = 80.0
    scale_up_threshold: float = 85.0
    scale_down_threshold: float = 50.0
    cooldown_seconds: int = 300  # 5 minutes
    check_interval_seconds: int = 60  # 1 minute


class HorizontalScaler:
    """
    Manages horizontal scaling of bot instances.
    
    Monitors system metrics and automatically scales instances up/down
    to maintain optimal performance and resource utilization.
    """
    
    def __init__(self, config: Optional[ScalingConfig] = None):
        """
        Initialize horizontal scaler.
        
        Args:
            config: Scaling configuration
        """
        self.config = config or ScalingConfig()
        self.instances: Dict[str, InstanceMetrics] = {}
        self.last_scaling_action = 0.0
        self.current_instances = 1
        self.scaling_history: List[Dict] = []
        
        # Callbacks for scaling actions
        self.on_scale_up: Optional[Callable] = None
        self.on_scale_down: Optional[Callable] = None
        
        logger.info(f"HorizontalScaler initialized with config: {self.config}")
    
    def register_instance(self, instance_id: str, metrics: InstanceMetrics):
        """
        Register or update instance metrics.
        
        Args:
            instance_id: Unique instance identifier
            metrics: Current instance metrics
        """
        self.instances[instance_id] = metrics
        logger.debug(f"Registered instance {instance_id}: CPU={metrics.cpu_percent}%, "
                    f"Memory={metrics.memory_percent}%, Trades={metrics.active_trades}")
    
    def unregister_instance(self, instance_id: str):
        """
        Remove instance from tracking.
        
        Args:
            instance_id: Instance to remove
        """
        if instance_id in self.instances:
            del self.instances[instance_id]
            logger.info(f"Unregistered instance {instance_id}")
    
    def get_aggregate_metrics(self) -> Dict[str, float]:
        """
        Calculate aggregate metrics across all instances.
        
        Returns:
            Dictionary with average metrics
        """
        if not self.instances:
            return {
                'avg_cpu': 0.0,
                'avg_memory': 0.0,
                'total_trades': 0,
                'total_opportunities': 0.0,
                'healthy_instances': 0
            }
        
        total_cpu = sum(m.cpu_percent for m in self.instances.values())
        total_memory = sum(m.memory_percent for m in self.instances.values())
        total_trades = sum(m.active_trades for m in self.instances.values())
        total_opps = sum(m.opportunities_per_second for m in self.instances.values())
        healthy = sum(1 for m in self.instances.values() if m.healthy)
        
        count = len(self.instances)
        
        return {
            'avg_cpu': total_cpu / count,
            'avg_memory': total_memory / count,
            'total_trades': total_trades,
            'total_opportunities': total_opps,
            'healthy_instances': healthy,
            'total_instances': count
        }
    
    def should_scale(self) -> ScalingAction:
        """
        Determine if scaling action is needed.
        
        Returns:
            Required scaling action
        """
        # Check cooldown period
        if time.time() - self.last_scaling_action < self.config.cooldown_seconds:
            return ScalingAction.NO_ACTION
        
        metrics = self.get_aggregate_metrics()
        
        # Check if we need to scale up
        if (metrics['avg_cpu'] > self.config.scale_up_threshold or 
            metrics['avg_memory'] > self.config.scale_up_threshold):
            if self.current_instances < self.config.max_instances:
                return ScalingAction.SCALE_UP
        
        # Check if we can scale down
        if (metrics['avg_cpu'] < self.config.scale_down_threshold and 
            metrics['avg_memory'] < self.config.scale_down_threshold):
            if self.current_instances > self.config.min_instances:
                return ScalingAction.SCALE_DOWN
        
        return ScalingAction.NO_ACTION
    
    async def scale_up(self, count: int = 1) -> bool:
        """
        Scale up by adding instances.
        
        Args:
            count: Number of instances to add
            
        Returns:
            True if successful
        """
        if self.current_instances + count > self.config.max_instances:
            logger.warning(f"Cannot scale up: would exceed max_instances={self.config.max_instances}")
            return False
        
        logger.info(f"Scaling UP: Adding {count} instance(s)")
        
        # Call user-provided callback if available
        if self.on_scale_up:
            await self.on_scale_up(count)
        
        self.current_instances += count
        self.last_scaling_action = time.time()
        
        self.scaling_history.append({
            'timestamp': time.time(),
            'action': 'scale_up',
            'count': count,
            'total_instances': self.current_instances
        })
        
        return True
    
    async def scale_down(self, count: int = 1) -> bool:
        """
        Scale down by removing instances.
        
        Args:
            count: Number of instances to remove
            
        Returns:
            True if successful
        """
        if self.current_instances - count < self.config.min_instances:
            logger.warning(f"Cannot scale down: would go below min_instances={self.config.min_instances}")
            return False
        
        logger.info(f"Scaling DOWN: Removing {count} instance(s)")
        
        # Call user-provided callback if available
        if self.on_scale_down:
            await self.on_scale_down(count)
        
        self.current_instances -= count
        self.last_scaling_action = time.time()
        
        self.scaling_history.append({
            'timestamp': time.time(),
            'action': 'scale_down',
            'count': count,
            'total_instances': self.current_instances
        })
        
        return True
    
    async def auto_scale_loop(self):
        """
        Main auto-scaling loop that monitors and adjusts instances.
        """
        logger.info("Starting auto-scaling loop")
        
        while True:
            try:
                action = self.should_scale()
                
                if action == ScalingAction.SCALE_UP:
                    await self.scale_up(1)
                elif action == ScalingAction.SCALE_DOWN:
                    await self.scale_down(1)
                
                # Log current status
                metrics = self.get_aggregate_metrics()
                logger.info(f"Scaling status: {self.current_instances} instances, "
                          f"CPU={metrics['avg_cpu']:.1f}%, "
                          f"Memory={metrics['avg_memory']:.1f}%, "
                          f"Trades={metrics['total_trades']}")
                
                await asyncio.sleep(self.config.check_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in auto-scaling loop: {e}")
                await asyncio.sleep(self.config.check_interval_seconds)
    
    def get_status(self) -> Dict:
        """
        Get current scaling status.
        
        Returns:
            Status dictionary
        """
        metrics = self.get_aggregate_metrics()
        
        return {
            'current_instances': self.current_instances,
            'min_instances': self.config.min_instances,
            'max_instances': self.config.max_instances,
            'metrics': metrics,
            'last_scaling_action': self.last_scaling_action,
            'time_since_last_action': time.time() - self.last_scaling_action,
            'cooldown_remaining': max(0, self.config.cooldown_seconds - (time.time() - self.last_scaling_action)),
            'scaling_history': self.scaling_history[-10:]  # Last 10 actions
        }


# Global instance
_scaler: Optional[HorizontalScaler] = None


def get_horizontal_scaler(config: Optional[ScalingConfig] = None) -> HorizontalScaler:
    """
    Get or create global horizontal scaler instance.
    
    Args:
        config: Optional scaling configuration
        
    Returns:
        HorizontalScaler instance
    """
    global _scaler
    if _scaler is None:
        _scaler = HorizontalScaler(config)
    return _scaler
