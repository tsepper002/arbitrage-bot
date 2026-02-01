#!/usr/bin/env python3
"""
MexcWS - MEXC WebSocket client with standardized interface.
Supports multiple symbols, depth subscription, and proper error handling.
Follows the same pattern as BybitWS, KucoinWS, and HtxWS.
"""
import json
import logging
import time
import random
import threading
from typing import List, Optional, Tuple, Dict
import websocket
import asyncio

logger = logging.getLogger("mexc_ws")

DEPTH_LEVELS = 20


def _safe_json_loads(msg) -> Optional[dict]:
    try:
        if isinstance(msg, (bytes, bytearray)):
            return json.loads(msg.decode())
        return json.loads(msg)
    except Exception:
        return None


class MexcWS:
    def __init__(
        self,
        symbols: List[str],
        price_store,
        loop: asyncio.AbstractEventLoop,
        exchange_name: str = "MEXC",
        stagger_start: float = 0.0,
    ):
        """
        Standardized constructor for MEXC WebSocket client.
        
        Args:
            symbols: List of symbols to subscribe (e.g., ["BTC-USDT", "ETH-USDT"])
            price_store: PriceStore instance for updating prices
            loop: asyncio event loop
            exchange_name: Name of the exchange (default: "MEXC")
            stagger_start: Delay before starting (for load balancing)
        """
        self.orig_symbols = symbols
        # MEXC часто использует формат BTC_USDT — заменяем дефис на подчеркивание
        self.symbols = [s.replace("-", "_") for s in symbols]
        self.symbol_map = {norm: orig for norm, orig in zip(self.symbols, symbols)}
        self.exchange = exchange_name
        self.price_store = price_store
        self.loop = loop
        self._stop = threading.Event()
        self._ws = None
        self._local_books: Dict[str, Dict[str, Dict[float, float]]] = {
            s: {"bids": {}, "asks": {}} for s in symbols
        }
        self._thread = threading.Thread(target=self._run, daemon=True)
        if stagger_start and stagger_start > 0:
            time.sleep(stagger_start * random.uniform(0.5, 1.5))
        self._thread.start()

    def _book_to_levels(self, book_side: Dict[float, float], side: str) -> List[Tuple[float, float]]:
        items = list(book_side.items())
        if side == "bids":
            items_sorted = sorted(items, key=lambda x: -x[0])[:DEPTH_LEVELS]
        else:
            items_sorted = sorted(items, key=lambda x: x[0])[:DEPTH_LEVELS]
        return [(float(p), float(s)) for p, s in items_sorted]

    def _on_open(self, ws):
        try:
            for sym in self.symbols:
                # Subscribe to depth updates
                sub = {
                    "method": "SUBSCRIPTION",
                    "params": [f"spot@public.limit.depth.v3.api@{sym}@20"]
                }
                ws.send(json.dumps(sub))
                logger.info(f"{self.exchange}: subscribed to depth for {sym}")
                time.sleep(0.05)
        except Exception:
            logger.exception("MEXC on_open error")

    def _on_message(self, ws, msg):
        data = _safe_json_loads(msg)
        if not data:
            logger.debug("MEXC: non-json or empty message")
            return

        logger.debug(f"MEXC raw: {str(data)[:400]}")
        try:
            # MEXC depth data format: {"d": {"bids": [[price, qty], ...], "asks": [[price, qty], ...]}, "s": "BTC_USDT"}
            if isinstance(data, dict) and "d" in data:
                payload = data["d"]
                symbol_norm = data.get("s")
                if not symbol_norm:
                    return
                
                # Map back to original symbol format
                orig_sym = self.symbol_map.get(symbol_norm)
                if not orig_sym:
                    # Try without underscore
                    for norm, orig in self.symbol_map.items():
                        if norm.replace("_", "") == symbol_norm.replace("_", ""):
                            orig_sym = orig
                            break
                if not orig_sym:
                    logger.debug(f"MEXC: unknown symbol {symbol_norm}")
                    return

                bids_arr = payload.get("bids", [])
                asks_arr = payload.get("asks", [])

                if bids_arr and asks_arr:
                    # Build local book levels
                    bids_levels = []
                    asks_levels = []
                    for item in bids_arr[:DEPTH_LEVELS]:
                        try:
                            p = float(item[0])
                            s = float(item[1])
                            if s > 0:
                                bids_levels.append((p, s))
                        except Exception:
                            continue
                    for item in asks_arr[:DEPTH_LEVELS]:
                        try:
                            p = float(item[0])
                            s = float(item[1])
                            if s > 0:
                                asks_levels.append((p, s))
                        except Exception:
                            continue

                    if bids_levels and asks_levels:
                        # Sort properly
                        bids_levels = sorted(bids_levels, key=lambda x: -x[0])[:DEPTH_LEVELS]
                        asks_levels = sorted(asks_levels, key=lambda x: x[0])[:DEPTH_LEVELS]
                        
                        logger.debug(f"MEXC depth for {orig_sym}: bids={len(bids_levels)} asks={len(asks_levels)}")
                        asyncio.run_coroutine_threadsafe(
                            self.price_store.update_levels(
                                self.exchange, orig_sym, bids_levels, asks_levels, time.time()
                            ),
                            self.loop
                        )
                        return

                # Fallback: if no depth, try ticker update
                if "lastPrice" in payload or "price" in payload:
                    price = payload.get("lastPrice") or payload.get("price")
                    try:
                        price_val = float(price)
                        asyncio.run_coroutine_threadsafe(
                            self.price_store.update(
                                self.exchange, orig_sym, price_val, None, price_val, None, time.time()
                            ),
                            self.loop
                        )
                    except Exception:
                        pass

        except Exception:
            logger.exception("MEXC processing error")

    def _on_error(self, ws, err):
        logger.warning(f"{self.exchange} WS error: {err}")

    def _on_close(self, ws, code, reason):
        logger.info(f"{self.exchange} WS closed: {code} {reason}")

    def _run(self):
        url = "wss://wbs.mexc.com/ws"
        backoff = 1.0
        while not self._stop.is_set():
            try:
                logger.info(f"{self.exchange}: connecting to {url}")
                ws = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws = ws
                ws.run_forever(ping_interval=20, ping_timeout=10)
                logger.warning(f"{self.exchange}: run_forever returned, will reconnect")
            except Exception:
                logger.exception("MEXC run error - reconnecting")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60.0)

    def stop(self):
        self._stop.set()
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
