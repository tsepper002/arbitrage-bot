#!/usr/bin/env python3
"""
Bybit single-connection WS client with orderbook snapshot + delta handling.
Работает с форматами, где depth приходит в полях 'b'/'a' или 'bids'/'asks'.
Публикует top DEPTH_LEVELS в PriceStore через update_levels.
Enhanced with health monitoring and reconnection support.
"""
import json
import threading
import time
import logging
from typing import List, Optional, Tuple, Dict
import websocket
import asyncio
import random
from .ws_helpers import WSHealthMonitor, WSReconnectHelper

logger = logging.getLogger("bybit_ws")
# Logging configured in main.py - don't override here

DEPTH_LEVELS = 20

def _safe_json_loads(msg) -> Optional[dict]:
    try:
        if isinstance(msg, (bytes, bytearray)):
            txt = msg.decode()
        else:
            txt = msg
        return json.loads(txt)
    except Exception:
        return None

class BybitWS:
    def __init__(self, symbols: List[str], price_store, loop: asyncio.AbstractEventLoop,
                 exchange_name: str = "Bybit", stagger_start: float = 0.0):
        self.orig_symbols = symbols
        self.symbols = [s.replace("-", "") for s in symbols]
        self.exchange = exchange_name
        self.price_store = price_store
        self.loop = loop
        self._stop = threading.Event()
        self._ws = None
        # local book maps: symbol -> {'bids': {price: size}, 'asks': {price: size}}
        self._local_books: Dict[str, Dict[str, Dict[float, float]]] = {sym: {"bids": {}, "asks": {}} for sym in symbols}
        
        # Add health monitoring
        self._health_monitor = WSHealthMonitor(exchange_name)
        self._reconnect_helper = WSReconnectHelper(exchange_name)
        
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

    def _apply_changes(self, sym: str, side: str, changes: List[List[float]]):
        book = self._local_books.get(sym)
        if not book:
            return
        side_map = book[side]
        for item in changes:
            try:
                p = float(item[0])
                s = float(item[1])
            except Exception:
                continue
            if s == 0.0:
                side_map.pop(p, None)
            else:
                side_map[p] = s

    def _on_open(self, ws):
        try:
            # Mark connection as healthy
            self._health_monitor.on_connection_start()
            self._reconnect_helper.on_successful_connection()
            
            ticker_args = [f"tickers.{s}" for s in self.symbols]
            ob_args = [f"orderbook.50.{s}" for s in self.symbols]
            args = ticker_args + ob_args
            max_chunk = 10
            for i in range(0, len(args), max_chunk):
                chunk = args[i:i+max_chunk]
                sub = {"op": "subscribe", "args": chunk}
                try:
                    ws.send(json.dumps(sub))
                    logger.info(f"{self.exchange}: sent subscribe chunk with {len(chunk)} args")
                    time.sleep(0.05)
                except Exception:
                    logger.exception("Bybit on_open send error for chunk")
        except Exception:
            logger.exception("Bybit on_open error")

    def _on_message(self, ws, msg):
        # Record message for health monitoring
        self._health_monitor.on_message_received()
        
        data = _safe_json_loads(msg)
        if not data:
            logger.debug("Bybit: non-json or empty message")
            return
        logger.debug(f"Bybit raw: {str(data)[:400]}")
        try:
            topic = data.get("topic", "") if isinstance(data, dict) else ""
            payload = data.get("data") if isinstance(data, dict) else None

            if payload and isinstance(payload, dict):
                # determine symbol
                sym = None
                if topic and "." in topic:
                    tok = topic.split(".")[-1]
                    for orig in self.orig_symbols:
                        if orig.replace("-", "") == tok:
                            sym = orig
                            break

                # Support multiple payload shapes:
                # 1) Bybit uses keys 'b' (bids) and 'a' (asks) in many messages
                # 2) Some APIs use 'bids'/'asks' naming
                # 3) Some use nested 'data' or 'tick' fields (handled elsewhere)
                # Handle snapshot: payload contains bids/asks or b/a
                bids_arr = None
                asks_arr = None

                if "b" in payload or "a" in payload:
                    bids_arr = payload.get("b", []) or payload.get("bids", [])
                    asks_arr = payload.get("a", []) or payload.get("asks", [])
                elif "bids" in payload or "asks" in payload:
                    bids_arr = payload.get("bids", [])
                    asks_arr = payload.get("asks", [])

                # If snapshot-style arrays present -> treat as snapshot (replace)
                if bids_arr is not None and asks_arr is not None:
                    bids_map = {}
                    asks_map = {}
                    # bids_arr and asks_arr can be lists of [price, size] (strings)
                    for it in bids_arr:
                        try:
                            p = float(it[0]); s = float(it[1])
                            if s > 0:
                                bids_map[p] = s
                        except Exception:
                            continue
                    for it in asks_arr:
                        try:
                            p = float(it[0]); s = float(it[1])
                            if s > 0:
                                asks_map[p] = s
                        except Exception:
                            continue
                    if not sym:
                        # try payload symbol field like s or symbol
                        sym_field = payload.get("s") or payload.get("symbol") or payload.get("symbolName")
                        if sym_field:
                            for orig in self.orig_symbols:
                                if orig.replace("-", "") == sym_field:
                                    sym = orig
                                    break
                    if sym:
                        # Track symbol-level health
                        self._health_monitor.on_message_received(sym)
                        
                        self._local_books[sym]["bids"] = bids_map
                        self._local_books[sym]["asks"] = asks_map
                        bids_levels = self._book_to_levels(bids_map, "bids")
                        asks_levels = self._book_to_levels(asks_map, "asks")
                        logger.debug(f"Bybit depth snapshot for {sym}: bids={len(bids_levels)} asks={len(asks_levels)}")
                        asyncio.run_coroutine_threadsafe(
                            self.price_store.update_levels(self.exchange, sym, bids_levels, asks_levels, time.time()),
                            self.loop
                        )
                        return

                # Handle delta updates: Bybit delta messages often have type 'delta' and data contains 'b' and 'a' arrays
                # Example: {'type':'delta','data':{'s':'BTCUSDT','b':[['89082.8','0'],...],'a':[['89101.1','1.2787'],...]}}
                if data.get("type") == "delta" and isinstance(payload, dict):
                    # payload keys likely 'b' and 'a' or 'bids'/'asks'
                    sym_field = payload.get("s") or payload.get("symbol") or payload.get("symbolName")
                    if not sym and sym_field:
                        for orig in self.orig_symbols:
                            if orig.replace("-", "") == sym_field:
                                sym = orig
                                break
                    if sym:
                        # apply bids changes (b)
                        b_changes = payload.get("b") or payload.get("bids") or []
                        a_changes = payload.get("a") or payload.get("asks") or []
                        if b_changes:
                            self._apply_changes(sym, "bids", b_changes)
                        if a_changes:
                            self._apply_changes(sym, "asks", a_changes)
                        bids_levels = self._book_to_levels(self._local_books[sym]["bids"], "bids")
                        asks_levels = self._book_to_levels(self._local_books[sym]["asks"], "asks")
                        asyncio.run_coroutine_threadsafe(
                            self.price_store.update_levels(self.exchange, sym, bids_levels, asks_levels, time.time()),
                            self.loop
                        )
                        return

                # Other fallback shapes: sometimes orderbook updates are in payload.data or nested — handle common ticker fallback
                if "lastPrice" in payload or "price" in payload or "last" in payload:
                    last = payload.get("lastPrice") or payload.get("price") or payload.get("last")
                    try:
                        val = float(last)
                    except Exception:
                        val = None
                    if not sym:
                        sym_field = payload.get("s") or payload.get("symbol") or payload.get("symbolName")
                        if sym_field:
                            for orig in self.orig_symbols:
                                if orig.replace("-", "") == sym_field:
                                    sym = orig
                                    break
                    if sym and val is not None:
                        logger.debug(f"Bybit -> update store (ticker): {sym} {val}")
                        asyncio.run_coroutine_threadsafe(
                            self.price_store.update(self.exchange, sym, val, None, val, None, time.time()),
                            self.loop
                        )
                        return

        except Exception:
            logger.exception("Bybit processing error")

    def _on_error(self, ws, err):
        logger.warning(f"{self.exchange} WS error: {err}")

    def _on_close(self, ws, code, reason):
        logger.info(f"{self.exchange} WS closed: {code} {reason}")

    def _run(self):
        url = "wss://stream.bybit.com/v5/public/spot"
        while not self._stop.is_set():
            try:
                # Check if reconnection should be attempted
                should_reconnect, reason = self._reconnect_helper.should_reconnect()
                if not should_reconnect:
                    logger.error(f"{self.exchange}: {reason}, stopping")
                    break
                
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
                
                # Mark as disconnected
                self._health_monitor.on_connection_close()
                
            except Exception as e:
                logger.exception(f"Bybit run error - reconnecting: {e}")
                self._health_monitor.on_connection_close()
            
            # Get reconnection delay with exponential backoff
            if not self._stop.is_set():
                delay = self._reconnect_helper.get_next_delay()
                time.sleep(delay)

    def stop(self):
        self._stop.set()
        self._health_monitor.on_connection_close()
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
    
    def get_health_status(self) -> dict:
        """Get current health status of this connection."""
        health = self._health_monitor.check_health()
        self._health_monitor.log_health_status()
        return health