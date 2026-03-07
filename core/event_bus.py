#!/usr/bin/env python3
"""
Lightweight async EventBus for decoupling trading system components.

Architecture pattern: Publish/Subscribe with typed events.
Components publish events without knowing who consumes them.
This eliminates direct coupling between modules.

Usage:
    bus = EventBus()

    # Subscribe to events
    bus.subscribe("price_update", my_handler)
    bus.subscribe("trade_executed", on_trade)

    # Publish events (fire-and-forget, non-blocking)
    await bus.publish("price_update", {"symbol": "BTC-USDT", "exchange": "Binance", "bid": 73000})

    # Or publish without await (queued for next event loop tick)
    bus.publish_sync("price_update", {"symbol": "BTC-USDT", ...})

Event Types:
    price_update      - New price data from exchange WS/REST
    opportunity_found - Arbitrage opportunity detected by scanner
    trade_executed    - Order successfully executed
    trade_failed      - Order execution failed
    balance_changed   - Exchange balance updated
    risk_alert        - Risk limit approached or breached
    coin_switched     - Active trading coin changed
    shutdown          - Graceful shutdown initiated
"""
import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

logger = logging.getLogger("EventBus")


@dataclass
class Event:
    """Typed event with metadata."""
    type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    source: str = ""


# Pre-defined event type constants
PRICE_UPDATE = "price_update"
OPPORTUNITY_FOUND = "opportunity_found"
TRADE_EXECUTED = "trade_executed"
TRADE_FAILED = "trade_failed"
BALANCE_CHANGED = "balance_changed"
RISK_ALERT = "risk_alert"
COIN_SWITCHED = "coin_switched"
SHUTDOWN = "shutdown"


class EventBus:
    """
    Lightweight async event bus for component decoupling.

    Features:
    - Async handlers called concurrently via asyncio.gather
    - Sync handlers called in-line (for simple logging/metrics)
    - Error isolation: one handler failure doesn't block others
    - Optional event history for debugging
    - Publish metrics: event counts and handler latencies
    """

    def __init__(self, max_history: int = 100):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._history: List[Event] = []
        self._max_history = max_history
        self._event_counts: Dict[str, int] = defaultdict(int)
        self._running = True

    def subscribe(self, event_type: str,
                  handler: Union[Callable, Coroutine]) -> None:
        """
        Subscribe a handler to an event type.

        Handler can be async (coroutine function) or sync (regular function).
        Both signatures: handler(event: Event) -> None
        """
        self._subscribers[event_type].append(handler)
        logger.debug(f"EventBus: {handler.__name__} subscribed to '{event_type}'")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Remove a handler from an event type."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            logger.debug(f"EventBus: {handler.__name__} unsubscribed from '{event_type}'")

    async def publish(self, event_type: str, data: Optional[Dict[str, Any]] = None,
                      source: str = "") -> None:
        """
        Publish an event to all subscribers.

        All handlers are called concurrently. Errors in one handler
        don't affect other handlers.
        """
        if not self._running:
            return

        event = Event(type=event_type, data=data or {}, source=source)
        self._event_counts[event_type] += 1

        # Store in history (ring buffer)
        if self._max_history > 0:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return

        # Separate async and sync handlers
        async_tasks = []
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    async_tasks.append(self._safe_call_async(handler, event))
                else:
                    self._safe_call_sync(handler, event)
            except Exception as e:
                logger.error(f"EventBus: Error preparing handler {handler.__name__}: {e}")

        # Run async handlers concurrently
        if async_tasks:
            await asyncio.gather(*async_tasks, return_exceptions=True)

    def publish_sync(self, event_type: str, data: Optional[Dict[str, Any]] = None,
                     source: str = "") -> None:
        """
        Non-blocking publish — schedules event for next event loop tick.
        Use when you can't await (e.g., from sync code or callbacks).
        """
        if not self._running:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.publish(event_type, data, source))
            else:
                logger.debug("EventBus: Event loop not running, event dropped")
        except RuntimeError:
            logger.debug("EventBus: No event loop available, event dropped")

    async def _safe_call_async(self, handler: Callable, event: Event) -> None:
        """Call an async handler with error isolation."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"EventBus: Handler {handler.__name__} failed on "
                f"'{event.type}': {e}", exc_info=False
            )

    def _safe_call_sync(self, handler: Callable, event: Event) -> None:
        """Call a sync handler with error isolation."""
        try:
            handler(event)
        except Exception as e:
            logger.error(
                f"EventBus: Sync handler {handler.__name__} failed on "
                f"'{event.type}': {e}", exc_info=False
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics for monitoring."""
        return {
            "total_events": sum(self._event_counts.values()),
            "event_counts": dict(self._event_counts),
            "subscriber_counts": {
                k: len(v) for k, v in self._subscribers.items() if v
            },
            "history_size": len(self._history),
        }

    def get_recent_events(self, event_type: Optional[str] = None,
                          limit: int = 10) -> List[Event]:
        """Get recent events, optionally filtered by type."""
        events = self._history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]

    def stop(self) -> None:
        """Stop accepting new events (for graceful shutdown)."""
        self._running = False
        logger.info("EventBus: Stopped accepting events")

    def reset(self) -> None:
        """Reset all subscriptions and history (for testing)."""
        self._subscribers.clear()
        self._history.clear()
        self._event_counts.clear()
        self._running = True
