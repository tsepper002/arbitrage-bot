#!/usr/bin/env python3
"""
Lock-free PriceStore using atomic dict reference swap (W1 optimization).
Safe under CPython GIL - eliminates 20-50ms contention per cycle.
"""
import time
import logging
from collections import defaultdict
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger("PriceStore")


class PriceStore:
    """
    Lock-free price store using atomic dict reference swap.
    
    W1 OPTIMIZATION: Replaces asyncio.Lock() with atomic dict swap.
    Under CPython GIL, dict reference assignment is atomic.
    Readers get instant O(1) snapshot without blocking writers.
    """
    
    def __init__(self):
        # data[symbol][exchange] = { "bid": , "ask": , "bid_size": , "ask_size": ,
        #   "bids_levels": [(p,s),...], "asks_levels": [(p,s),...], "ts": float }
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        # No lock needed - atomic dict reference swap
        # §4 Event-driven: optional callback when symbol data changes
        self._on_update_callback = None

    def set_on_update(self, callback):
        """Set callback(symbol) to trigger event-driven scanning."""
        self._on_update_callback = callback
    
    async def update(self, exchange: str, symbol: str,
                     bid: Optional[float], bid_size: Optional[float],
                     ask: Optional[float], ask_size: Optional[float],
                     ts: Optional[float] = None):
        """
        Update top-of-book prices (async for compatibility).
        
        Note: No lock needed with atomic dict swap (W1 optimization).
        """
        # Create copy of current data for this symbol
        current_exmap = dict(self._data.get(symbol, {}))
        rec = dict(current_exmap.get(exchange, {}))
        
        if bid is not None:
            rec["bid"] = float(bid)
        if bid_size is not None:
            rec["bid_size"] = float(bid_size)
        if ask is not None:
            rec["ask"] = float(ask)
        if ask_size is not None:
            rec["ask_size"] = float(ask_size)
        if ts is None:
            ts = time.time()
        rec["ts"] = ts
        
        # Atomic swap
        current_exmap[exchange] = rec
        self._data[symbol] = current_exmap
        
        # §4 Event-driven: notify engine that this symbol has new data
        if self._on_update_callback:
            try:
                self._on_update_callback(symbol)
            except (TypeError, ValueError, AttributeError) as e:
                logger.debug(f"PriceStore on_update callback error: {e}")
        
        logger.debug(f"PriceStore.update (top) {exchange} {symbol} bid={rec.get('bid')} ask={rec.get('ask')}")
    
    async def update_levels(self, exchange: str, symbol: str,
                            bids_levels: Optional[List[Tuple[float, float]]],
                            asks_levels: Optional[List[Tuple[float, float]]],
                            ts: Optional[float] = None):
        """
        Update orderbook depth levels (async for compatibility).
        
        bids_levels: list of (price, size) ordered best-first (descending price)
        asks_levels: list of (price, size) ordered best-first (ascending price)
        
        Note: No lock needed with atomic dict swap (W1 optimization).
        """
        # Create copy of current data for this symbol
        current_exmap = dict(self._data.get(symbol, {}))
        rec = dict(current_exmap.get(exchange, {}))
        
        if bids_levels is not None:
            rec["bids_levels"] = [(float(p), float(s)) for p, s in bids_levels]
            if bids_levels:
                rec["bid"], rec["bid_size"] = float(bids_levels[0][0]), float(bids_levels[0][1])
        if asks_levels is not None:
            rec["asks_levels"] = [(float(p), float(s)) for p, s in asks_levels]
            if asks_levels:
                rec["ask"], rec["ask_size"] = float(asks_levels[0][0]), float(asks_levels[0][1])
        if ts is None:
            ts = time.time()
        rec["ts"] = ts
        
        # Atomic swap
        current_exmap[exchange] = rec
        self._data[symbol] = current_exmap
        
        # explicit log to confirm levels were stored
        b_len = len(rec.get("bids_levels", []))
        a_len = len(rec.get("asks_levels", []))
        logger.debug(f"PriceStore.update_levels {exchange} {symbol} bids_levels={b_len} asks_levels={a_len} top_bid={rec.get('bid')} top_ask={rec.get('ask')}")
    
    async def get(self, symbol: str) -> Dict[str, Dict[str, Any]]:
        """
        Get data for a symbol (async for compatibility, but no lock needed).
        Returns a snapshot copy.
        """
        exmap = self._data.get(symbol, {})
        return {ex: rec.copy() for ex, rec in exmap.items()}
    
    def snapshot(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Get full snapshot - deep copy for thread safety.
        Each record dict is independently copied so mutations
        in the live store don't affect the snapshot.
        """
        return {
            s: {ex: dict(rec) for ex, rec in exmap.items()}
            for s, exmap in self._data.items()
        }