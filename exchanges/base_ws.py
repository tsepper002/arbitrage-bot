#!/usr/bin/env python3
"""
Base WebSocket client with automatic reconnection, exponential backoff, and health monitoring.
Provides a robust foundation for exchange-specific WebSocket implementations.
"""
import time
import logging
import threading
from typing import Optional, Callable
from abc import ABC, abstractmethod
import settings

logger = logging.getLogger("base_ws")


class BaseWebSocket(ABC):
    """
    Base class for WebSocket connections with:
    - Automatic reconnection with exponential backoff
    - Connection health monitoring
    - Stream staleness detection
    """
    
    def __init__(self, exchange_name: str):
        """
        Initialize base WebSocket client.
        
        Args:
            exchange_name: Name of the exchange (for logging)
        """
        self.exchange_name = exchange_name
        self._stop = threading.Event()
        self._ws = None
        self._thread: Optional[threading.Thread] = None
        
        # Reconnection state
        self._reconnect_attempts = 0
        self._current_reconnect_delay = settings.WS_RECONNECT_DELAY_SEC
        self._last_successful_connection = 0.0
        
        # Health monitoring
        self._last_message_time = {}  # symbol -> last update timestamp
        self._connection_start_time = None
        self._total_messages_received = 0
        self._last_health_check = time.time()
        
        logger.info(f"{self.exchange_name}: BaseWebSocket initialized")
    
    def start(self):
        """Start the WebSocket connection in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning(f"{self.exchange_name}: Already running")
            return
        
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_with_reconnect, daemon=True)
        self._thread.start()
        logger.info(f"{self.exchange_name}: Background thread started")
    
    def stop(self):
        """Stop the WebSocket connection."""
        logger.info(f"{self.exchange_name}: Stopping...")
        self._stop.set()
        
        if self._ws:
            try:
                self._ws.close()
            except Exception as e:
                logger.debug(f"{self.exchange_name}: Error closing WebSocket: {e}")
        
        if self._thread:
            self._thread.join(timeout=5.0)
        
        logger.info(f"{self.exchange_name}: Stopped")
    
    def _run_with_reconnect(self):
        """Main loop with automatic reconnection."""
        while not self._stop.is_set():
            try:
                logger.info(f"{self.exchange_name}: Attempting connection...")
                self._connection_start_time = time.time()
                self._connect_and_run()
                
                # Connection closed normally
                if self._stop.is_set():
                    break
                
                # Unexpected disconnect - reconnect if enabled
                if settings.WS_AUTO_RECONNECT:
                    self._handle_reconnect()
                else:
                    logger.warning(f"{self.exchange_name}: Auto-reconnect disabled, stopping")
                    break
                    
            except Exception as e:
                logger.exception(f"{self.exchange_name}: Error in main loop: {e}")
                
                if settings.WS_AUTO_RECONNECT and not self._stop.is_set():
                    self._handle_reconnect()
                else:
                    break
    
    def _handle_reconnect(self):
        """Handle reconnection with exponential backoff."""
        self._reconnect_attempts += 1
        
        # Check max attempts
        if settings.WS_MAX_RECONNECT_ATTEMPTS > 0:
            if self._reconnect_attempts >= settings.WS_MAX_RECONNECT_ATTEMPTS:
                logger.error(
                    f"{self.exchange_name}: Max reconnect attempts "
                    f"({settings.WS_MAX_RECONNECT_ATTEMPTS}) reached, giving up"
                )
                return
        
        # Calculate delay with exponential backoff
        delay = min(
            self._current_reconnect_delay,
            settings.WS_MAX_RECONNECT_DELAY_SEC
        )
        
        logger.warning(
            f"{self.exchange_name}: Reconnecting in {delay:.1f}s "
            f"(attempt {self._reconnect_attempts})"
        )
        
        # Wait before reconnecting (check stop flag periodically)
        start_wait = time.time()
        while time.time() - start_wait < delay:
            if self._stop.is_set():
                return
            time.sleep(0.5)
        
        # Increase delay for next attempt
        self._current_reconnect_delay *= settings.WS_RECONNECT_BACKOFF_MULTIPLIER
    
    def _on_successful_connection(self):
        """Called when connection is successfully established."""
        self._last_successful_connection = time.time()
        self._reconnect_attempts = 0
        self._current_reconnect_delay = settings.WS_RECONNECT_DELAY_SEC
        logger.info(f"{self.exchange_name}: Successfully connected")
    
    def _record_message(self, symbol: Optional[str] = None):
        """Record that a message was received (for staleness detection)."""
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
        is_connected = self._ws is not None and hasattr(self._ws, 'connected') and self._ws.connected
        uptime = current_time - self._connection_start_time if self._connection_start_time else 0
        
        # Check for stale streams
        stale_symbols = []
        for symbol, last_time in self._last_message_time.items():
            time_since_update = current_time - last_time
            if time_since_update > settings.STREAM_STALENESS_THRESHOLD_SEC:
                stale_symbols.append((symbol, time_since_update))
        
        health = {
            'exchange': self.exchange_name,
            'connected': is_connected,
            'uptime_seconds': uptime,
            'reconnect_attempts': self._reconnect_attempts,
            'total_messages': self._total_messages_received,
            'tracked_symbols': len(self._last_message_time),
            'stale_symbols': stale_symbols,
            'is_healthy': is_connected and len(stale_symbols) == 0
        }
        
        # Log warnings for stale streams
        if stale_symbols:
            for symbol, staleness in stale_symbols:
                logger.warning(
                    f"{self.exchange_name}: Stream for {symbol} is stale "
                    f"({staleness:.0f}s since last update)"
                )
        
        return health
    
    def log_health_status(self):
        """Log current health status (called periodically)."""
        current_time = time.time()
        
        # Only log at configured interval
        if current_time - self._last_health_check < settings.HEALTH_CHECK_INTERVAL_SEC:
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
    
    # Abstract methods to be implemented by subclasses
    
    @abstractmethod
    def _connect_and_run(self):
        """
        Establish WebSocket connection and run message loop.
        Should call _on_successful_connection() when connected.
        Should call _record_message() for each message received.
        Should respect _stop flag and exit when set.
        """
        pass
    
    @abstractmethod
    def _on_message(self, ws, message):
        """Handle incoming WebSocket message."""
        pass
    
    def _on_error(self, ws, error):
        """Handle WebSocket error."""
        logger.error(f"{self.exchange_name}: WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code=None, close_msg=None):
        """Handle WebSocket close."""
        logger.warning(
            f"{self.exchange_name}: WebSocket closed "
            f"(code={close_status_code}, msg={close_msg})"
        )
    
    def _on_open(self, ws):
        """Handle WebSocket open."""
        self._on_successful_connection()
