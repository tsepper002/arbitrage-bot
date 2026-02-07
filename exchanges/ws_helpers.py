#!/usr/bin/env python3
"""
WebSocket health monitor and reconnection helper.
Provides health monitoring and reconnection capabilities that can be added to existing WS clients.
"""
import time
import logging
from typing import Dict, Optional, Callable
import settings

logger = logging.getLogger("ws_health")


class WSHealthMonitor:
    """
    Health monitoring for WebSocket connections.
    Tracks message timestamps, detects stale streams, and provides health status.
    """
    
    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name
        self._last_message_time: Dict[str, float] = {}  # symbol -> last update timestamp
        self._connection_start_time: Optional[float] = None
        self._total_messages_received = 0
        self._last_health_check = time.time()
        self._is_connected = False
    
    def on_connection_start(self):
        """Call when connection is established."""
        self._connection_start_time = time.time()
        self._is_connected = True
        logger.info(f"✅ {self.exchange_name}: Connected")
    
    def on_connection_close(self):
        """Call when connection is closed."""
        self._is_connected = False
        logger.warning(f"❌ {self.exchange_name}: Disconnected")
    
    def on_message_received(self, symbol: Optional[str] = None):
        """
        Call when a message is received.
        
        Args:
            symbol: Optional symbol identifier for staleness tracking
        """
        current_time = time.time()
        self._total_messages_received += 1
        
        if symbol:
            self._last_message_time[symbol] = current_time
    
    def check_health(self) -> dict:
        """
        Check connection health and stream staleness.
        
        Returns:
            Dict with health status information
        """
        current_time = time.time()
        
        # Basic connection info
        uptime = current_time - self._connection_start_time if self._connection_start_time else 0
        
        # Check for stale streams
        stale_symbols = []
        for symbol, last_time in self._last_message_time.items():
            time_since_update = current_time - last_time
            if time_since_update > settings.STREAM_STALENESS_THRESHOLD_SEC:
                stale_symbols.append((symbol, time_since_update))
        
        is_healthy = self._is_connected and len(stale_symbols) == 0
        
        return {
            'exchange': self.exchange_name,
            'connected': self._is_connected,
            'uptime_seconds': uptime,
            'total_messages': self._total_messages_received,
            'tracked_symbols': len(self._last_message_time),
            'stale_symbols': stale_symbols,
            'is_healthy': is_healthy
        }
    
    def log_health_status(self, force: bool = False):
        """
        Log current health status (throttled by HEALTH_CHECK_INTERVAL_SEC).
        
        Args:
            force: If True, log regardless of interval
        """
        current_time = time.time()
        
        # Check interval
        if not force and current_time - self._last_health_check < settings.HEALTH_CHECK_INTERVAL_SEC:
            return
        
        self._last_health_check = current_time
        health = self.check_health()
        
        status_icon = "✅" if health['is_healthy'] else "⚠️"
        logger.info(
            f"{status_icon} {self.exchange_name} Health: "
            f"Connected={health['connected']}, "
            f"Uptime={health['uptime_seconds']:.0f}s, "
            f"Messages={health['total_messages']}, "
            f"Symbols={health['tracked_symbols']}, "
            f"Stale={len(health['stale_symbols'])}"
        )
        
        # Log stale symbols as warnings
        for symbol, staleness in health['stale_symbols']:
            logger.warning(
                f"{self.exchange_name}: Stream for {symbol} is stale "
                f"({staleness:.0f}s since last update)"
            )


class WSReconnectHelper:
    """
    Helper for managing WebSocket reconnections with exponential backoff.
    """
    
    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name
        self._reconnect_attempts = 0
        self._current_delay = settings.WS_RECONNECT_DELAY_SEC
        self._last_successful_connection = 0.0
    
    def on_successful_connection(self):
        """Call when connection is successfully established."""
        self._last_successful_connection = time.time()
        self._reconnect_attempts = 0
        self._current_delay = settings.WS_RECONNECT_DELAY_SEC
        logger.info(f"{self.exchange_name}: Connection successful, reset reconnect counter")
    
    def should_reconnect(self) -> tuple[bool, Optional[str]]:
        """
        Check if reconnection should be attempted.
        
        Returns:
            (should_reconnect, reason) tuple
        """
        if not settings.WS_AUTO_RECONNECT:
            return False, "Auto-reconnect disabled"
        
        if settings.WS_MAX_RECONNECT_ATTEMPTS > 0:
            if self._reconnect_attempts >= settings.WS_MAX_RECONNECT_ATTEMPTS:
                return False, f"Max reconnect attempts ({settings.WS_MAX_RECONNECT_ATTEMPTS}) reached"
        
        return True, None
    
    def get_next_delay(self) -> float:
        """
        Get the delay for the next reconnection attempt with exponential backoff.
        
        Returns:
            Delay in seconds
        """
        self._reconnect_attempts += 1
        delay = min(self._current_delay, settings.WS_MAX_RECONNECT_DELAY_SEC)
        
        logger.info(
            f"{self.exchange_name}: Reconnecting in {delay:.1f}s "
            f"(attempt {self._reconnect_attempts})"
        )
        
        # Increase delay for next attempt
        self._current_delay *= settings.WS_RECONNECT_BACKOFF_MULTIPLIER
        
        return delay
    
    def reset(self):
        """Reset reconnection state."""
        self._reconnect_attempts = 0
        self._current_delay = settings.WS_RECONNECT_DELAY_SEC
