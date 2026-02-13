#!/usr/bin/env python3
"""
MEXC WebSocket client with orderbook snapshot + delta handling.
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

logger = logging.getLogger("mexc_ws")

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


class MexcWS:
    def __init__(self, symbols: List[str], price_store, loop: asyncio.AbstractEventLoop,
                 exchange_name: str = "MEXC", stagger_start: float = 0.0):
        self.orig_symbols = symbols
        # MEXC uses format: BTCUSDT (no separator)
        self.symbols = [s.replace("-", "") for s in symbols]
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

    def _normalize_symbol(self, mexc_symbol: str) -> Optional[str]:
        """Convert MEXC symbol format to our internal format."""
        # MEXC uses BTCUSDT, we use BTC-USDT
        for orig in self.orig_symbols:
            if orig.replace("-", "") == mexc_symbol:
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
            
            # Subscribe to depth and ticker for each symbol
            # MEXC format: {"method":"SUBSCRIPTION","params":["spot@public.depth.v3.api@BTCUSDT"]}
            for mexc_sym in self.symbols:
                # Subscribe to depth (orderbook)
                depth_sub = {
                    "method": "SUBSCRIPTION",
                    "params": [f"spot@public.depth.v3.api@{mexc_sym}"]
                }
                try:
                    ws.send(json.dumps(depth_sub))
                    logger.info(f"{self.exchange}: subscribed to depth for {mexc_sym}")
                    time.sleep(0.05)
                except Exception:
                    logger.exception(f"MEXC on_open send error for {mexc_sym}")
                
                # Subscribe to ticker
                ticker_sub = {
                    "method": "SUBSCRIPTION",
                    "params": [f"spot@public.deals.v3.api@{mexc_sym}"]
                }
                try:
                    ws.send(json.dumps(ticker_sub))
                    logger.info(f"{self.exchange}: subscribed to ticker for {mexc_sym}")
                    time.sleep(0.05)
                except Exception:
                    logger.exception(f"MEXC ticker sub error for {mexc_sym}")
        except Exception:
            logger.exception("MEXC on_open error")

    def _on_message(self, ws, msg):
        # Record message for health monitoring
        self._health_monitor.on_message_received()
        
        data = _safe_json_loads(msg)
        if not data:
            logger.debug("MEXC: non-json or empty message")
            return
        
        logger.debug(f"MEXC raw: {str(data)[:400]}")
        
        try:
            # Handle ping/pong
            if isinstance(data, dict) and data.get("msg") == "PING":
                pong_msg = {"msg": "PONG"}
                try:
                    ws.send(json.dumps(pong_msg))
                    logger.debug(f"MEXC: sent PONG")
                except Exception as e:
                    logger.warning(f"MEXC: failed to send pong: {e}")
                return
            
            # Handle subscription confirmation
            if isinstance(data, dict) and data.get("msg") == "COMMAND" and data.get("code") == 0:
                logger.info(f"MEXC: subscription confirmed")
                return
            
            # Handle data messages
            # MEXC format: {"c":"spot@public.depth.v3.api@BTCUSDT","d":{"asks":[[...]],"bids":[[...]]},"s":"BTCUSDT","t":...}
            if isinstance(data, dict) and "d" in data:
                channel = data.get("c", "")
                payload = data.get("d", {})
                mexc_symbol = data.get("s")
                
                if not isinstance(payload, dict) or not mexc_symbol:
                    return
                
                sym = self._normalize_symbol(mexc_symbol)
                if not sym:
                    logger.debug(f"MEXC: unknown symbol {mexc_symbol}")
                    return
                
                # Track symbol-level health
                self._health_monitor.on_message_received(sym)
                
                # Handle depth updates
                if "depth" in channel:
                    bids_arr = payload.get("bids") or []
                    asks_arr = payload.get("asks") or []
                    
                    if bids_arr or asks_arr:
                        # MEXC typically sends full snapshots
                        bids_map = {}
                        asks_map = {}
                        for it in bids_arr:
                            try:
                                p = float(it["p"]) if isinstance(it, dict) else float(it[0])
                                s = float(it["v"]) if isinstance(it, dict) else float(it[1])
                                if s > 0:
                                    bids_map[p] = s
                            except Exception:
                                continue
                        for it in asks_arr:
                            try:
                                p = float(it["p"]) if isinstance(it, dict) else float(it[0])
                                s = float(it["v"]) if isinstance(it, dict) else float(it[1])
                                if s > 0:
                                    asks_map[p] = s
                            except Exception:
                                continue
                        
                        self._local_books[sym]["bids"] = bids_map
                        self._local_books[sym]["asks"] = asks_map
                        logger.debug(f"MEXC depth snapshot for {sym}: bids={len(bids_map)} asks={len(asks_map)}")
                        
                        # Update price store with top levels
                        bids_levels = self._book_to_levels(bids_map, "bids")
                        asks_levels = self._book_to_levels(asks_map, "asks")
                        
                        asyncio.run_coroutine_threadsafe(
                            self.price_store.update_levels(self.exchange, sym, bids_levels, asks_levels, time.time()),
                            self.loop
                        )
                        return
                
                # Handle ticker/deals updates
                if "deals" in channel:
                    # MEXC deals format: {"d":{"deals":[{"p":"43215.5","v":"0.01","S":1,...}]},"s":"BTCUSDT"}
                    deals = payload.get("deals") or []
                    if deals and isinstance(deals, list) and len(deals) > 0:
                        last_deal = deals[-1]  # Get most recent deal
                        if isinstance(last_deal, dict):
                            last_price = last_deal.get("p")
                            if last_price:
                                try:
                                    val = float(last_price)
                                    logger.debug(f"MEXC ticker for {sym}: {val}")
                                    asyncio.run_coroutine_threadsafe(
                                        self.price_store.update(self.exchange, sym, val, None, val, None, time.time()),
                                        self.loop
                                    )
                                except Exception:
                                    pass
                    return
            
        except Exception:
            logger.exception("MEXC processing error")

    def _on_error(self, ws, err):
        logger.warning(f"{self.exchange} WS error: {err}")

    def _on_close(self, ws, code, reason):
        logger.info(f"{self.exchange} WS closed: {code} {reason}")

    def _run(self):
        url = "wss://wbs.mexc.com/ws"
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
                logger.exception(f"MEXC run error - reconnecting: {e}")
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
