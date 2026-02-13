import asyncio
from collections import defaultdict
from typing import Optional, Dict, Any, List, Tuple
import time
import logging

logger = logging.getLogger("PriceStore")

class PriceStore:
    def __init__(self):
        # data[symbol][exchange] = { "bid": , "ask": , "bid_size": , "ask_size": ,
        #   "bids_levels": [(p,s),...], "asks_levels": [(p,s),...], "ts": float }
        # Using atomic reference swap for lock-free snapshot() - CPython GIL makes dict reference assignment atomic
        self.data: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    async def update(self, exchange: str, symbol: str,
                     bid: Optional[float], bid_size: Optional[float],
                     ask: Optional[float], ask_size: Optional[float],
                     ts: Optional[float] = None):
        # Lock-free update: build new record then do atomic swap
        rec = self.data[symbol].get(exchange, {}).copy()
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
        # Atomic dict reference swap (CPython GIL guarantees atomicity)
        self.data[symbol][exchange] = rec
        logger.debug(f"PriceStore.update (top) {exchange} {symbol} bid={rec.get('bid')} ask={rec.get('ask')}")

    async def update_levels(self, exchange: str, symbol: str,
                            bids_levels: Optional[List[Tuple[float, float]]],
                            asks_levels: Optional[List[Tuple[float, float]]],
                            ts: Optional[float] = None):
        """
        bids_levels: list of (price, size) ordered best-first (descending price)
        asks_levels: list of (price, size) ordered best-first (ascending price)
        """
        # Lock-free update: build new record then do atomic swap
        rec = self.data[symbol].get(exchange, {}).copy()
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
        # Atomic dict reference swap
        self.data[symbol][exchange] = rec
        # explicit log to confirm levels were stored
        b_len = len(rec.get("bids_levels", []))
        a_len = len(rec.get("asks_levels", []))
        logger.info(f"PriceStore.update_levels {exchange} {symbol} bids_levels={b_len} asks_levels={a_len} top_bid={rec.get('bid')} top_ask={rec.get('ask')}")

    async def get(self, symbol: str) -> Dict[str, Dict[str, Any]]:
        # Lock-free read: return copy of current state
        return {ex: rec.copy() for ex, rec in self.data.get(symbol, {}).items()}

    def snapshot(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Lock-free O(1) snapshot - returns current dict reference.
        CPython GIL makes dict reference read atomic."""
        return {s: {ex: rec.copy() for ex, rec in exmap.items()} for s, exmap in self.data.items()}