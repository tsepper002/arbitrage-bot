#!/usr/bin/env python3
"""
XT.com WebSocket client with orderbook snapshot + delta handling.
Follows the same pattern as bybit_ws.py for consistency.
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

logger = logging.getLogger("xt_ws")

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


class XtWS:
    def __init__(self, symbols: List[str], price_store, loop: asyncio.AbstractEventLoop,
                 exchange_name: str = "XT", stagger_start: float = 0.0):
        self.orig_symbols = symbols
        # XT uses underscore format: BTC-USDT -> btc_usdt (lowercase)
        self.symbols = [s.replace("-", "_").lower() for s in symbols]
        self.exchange = exchange_name
        self.price_store = price_store
        self.loop = loop
        self._stop = threading.Event()
        self._ws = None
        # local book maps: symbol -> {'bids': {price: size}, 'asks': {price: size}}
        self._local_books: Dict[str, Dict[str, Dict[float, float]]] = {
            orig: {"bids": {}, "asks": {}} for orig in self.orig_symbols
        }
        
        # Add health monitoring
        self._health_monitor = WSHealthMonitor(exchange_name)
        self._reconnect_helper = WSReconnectHelper(exchange_name)
        
        self._thread = threading.Thread(target=self._run, daemon=True)
        if stagger_start and stagger_start > 0:
            time.sleep(stagger_start * random.uniform(0.5, 1.5))
        self._thread.start()

    def _normalize_symbol(self, xt_symbol: str) -> Optional[str]:
        """Convert XT symbol format to our internal format."""
        # XT uses btc_usdt, we use BTC-USDT
        for orig in self.orig_symbols:
            if orig.replace("-", "_").lower() == xt_symbol.lower():
                return orig
        return None

    def _book_to_levels(self, book_side: Dict[float, float], side: str) -> List[Tuple[float, float]]:
        items = list(book_side.items())
        if side == "bids":
            items_sorted = sorted(items, key=lambda x: -x[0])[:DEPTH_LEVELS]
        else:
            items_sorted = sorted(items, key=lambda x: x[0])[:DEPTH_LEVELS]
        return [(float(p), float(s)) for p, s in items_sorted]

    def _apply_changes(self, sym: str, side: str, changes: List[List]):
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
            
            # Subscribe to depth updates for each symbol
            # XT.com format: {"method":"subscribe","params":["btc_usdt@depth"],"id":1}
            for i, xt_sym in enumerate(self.symbols):
                sub = {
                    "method": "subscribe",
                    "params": [f"{xt_sym}@depth", f"{xt_sym}@ticker"],
                    "id": i + 1
                }
                try:
                    ws.send(json.dumps(sub))
                    logger.info(f"{self.exchange}: subscribed to {xt_sym}@depth and @ticker")
                    time.sleep(0.05)
                except Exception:
                    logger.exception(f"XT on_open send error for {xt_sym}")
        except Exception:
            logger.exception("XT on_open error")

    def _on_message(self, ws, msg):
        # Record message for health monitoring
        self._health_monitor.on_message_received()
        
        data = _safe_json_loads(msg)
        if not data:
            logger.debug("XT: non-json or empty message")
            return
        
        logger.debug(f"XT raw: {str(data)[:400]}")
        
        try:
            # Handle ping/pong
            if isinstance(data, dict) and data.get("ping"):
                pong_msg = {"pong": data["ping"]}
                try:
                    ws.send(json.dumps(pong_msg))
                    logger.debug(f"XT: sent pong")
                except Exception as e:
                    logger.warning(f"XT: failed to send pong: {e}")
                return
            
            # Handle subscription confirmation
            if isinstance(data, dict) and data.get("result") is None and "id" in data:
                logger.info(f"XT: subscription confirmed (id={data.get('id')})")
                return
            
            # Handle data messages
            # XT format: {"stream":"btc_usdt@depth","data":{"b":[...],"a":[...],"s":"btc_usdt"}}
            # or {"stream":"btc_usdt@ticker","data":{"c":"43215.5","s":"btc_usdt",...}}
            if isinstance(data, dict) and "stream" in data and "data" in data:
                stream = data.get("stream", "")
                payload = data.get("data", {})
                
                if not isinstance(payload, dict):
                    return
                
                # Extract symbol from stream or payload
                xt_symbol = None
                if "@" in stream:
                    xt_symbol = stream.split("@")[0]
                else:
                    xt_symbol = payload.get("s") or payload.get("symbol")
                
                if not xt_symbol:
                    logger.debug("XT: no symbol in message")
                    return
                
                sym = self._normalize_symbol(xt_symbol)
                if not sym:
                    logger.debug(f"XT: unknown symbol {xt_symbol}")
                    return
                
                # Track symbol-level health
                self._health_monitor.on_message_received(sym)
                
                # Handle depth updates
                if "@depth" in stream or "b" in payload or "a" in payload:
                    bids_arr = payload.get("b") or payload.get("bids") or []
                    asks_arr = payload.get("a") or payload.get("asks") or []
                    
                    if bids_arr or asks_arr:
                        # Check if this is a snapshot (large arrays) or delta (small arrays)
                        is_snapshot = len(bids_arr) > 10 or len(asks_arr) > 10
                        
                        if is_snapshot:
                            # Full snapshot - replace entire book
                            bids_map = {}
                            asks_map = {}
                            for it in bids_arr:
                                try:
                                    p = float(it[0])
                                    s = float(it[1])
                                    if s > 0:
                                        bids_map[p] = s
                                except Exception:
                                    continue
                            for it in asks_arr:
                                try:
                                    p = float(it[0])
                                    s = float(it[1])
                                    if s > 0:
                                        asks_map[p] = s
                                except Exception:
                                    continue
                            
                            self._local_books[sym]["bids"] = bids_map
                            self._local_books[sym]["asks"] = asks_map
                            logger.debug(f"XT depth snapshot for {sym}: bids={len(bids_map)} asks={len(asks_map)}")
                        else:
                            # Delta update - apply changes
                            if bids_arr:
                                self._apply_changes(sym, "bids", bids_arr)
                            if asks_arr:
                                self._apply_changes(sym, "asks", asks_arr)
                            logger.debug(f"XT depth delta for {sym}: bids={len(bids_arr)} asks={len(asks_arr)}")
                        
                        # Update price store with top levels
                        bids_levels = self._book_to_levels(self._local_books[sym]["bids"], "bids")
                        asks_levels = self._book_to_levels(self._local_books[sym]["asks"], "asks")
                        
                        asyncio.run_coroutine_threadsafe(
                            self.price_store.update_levels(self.exchange, sym, bids_levels, asks_levels, time.time()),
                            self.loop
                        )
                        return
                
                # Handle ticker updates
                if "@ticker" in stream:
                    # XT ticker format: {"c":"43215.5","o":"42800","h":"43500","l":"42500",...}
                    last_price = payload.get("c") or payload.get("last") or payload.get("lastPrice")
                    if last_price:
                        try:
                            val = float(last_price)
                            logger.debug(f"XT ticker for {sym}: {val}")
                            asyncio.run_coroutine_threadsafe(
                                self.price_store.update(self.exchange, sym, val, None, val, None, time.time()),
                                self.loop
                            )
                        except Exception:
                            pass
                    return
            
        except Exception:
            logger.exception("XT processing error")

    def _on_error(self, ws, err):
        logger.warning(f"{self.exchange} WS error: {err}")

    def _on_close(self, ws, code, reason):
        logger.info(f"{self.exchange} WS closed: {code} {reason}")

    def _run(self):
        url = "wss://stream.xt.com/public"
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
                logger.exception(f"XT run error - reconnecting: {e}")
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
