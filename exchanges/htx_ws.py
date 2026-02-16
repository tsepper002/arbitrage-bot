#!/usr/bin/env python3
"""
HTX / Huobi WS client with depth subscription and delta handling.

- single WS connection subscribes to ticker + depth (step0)
- supports application-level ping/pong (Huobi style)
- maintains a local book (price -> size) per symbol and publishes top DEPTH_LEVELS
  via price_store.update_levels(exchange, symbol, bids_levels, asks_levels, ts)
- handles snapshot messages (tick with bids/asks) and incremental updates (applies changes)
Enhanced with health monitoring and reconnection support.
"""
import json
import gzip
import threading
import time
import logging
from typing import List, Optional, Tuple, Dict, Any
import random
import websocket
import asyncio
from .ws_helpers import WSHealthMonitor, WSReconnectHelper

logger = logging.getLogger("htx_ws")
# Logging configured in main.py - don't override here

DEPTH_LEVELS = 20


def _safe_json_loads(msg: Any) -> Optional[dict]:
    try:
        if isinstance(msg, (bytes, bytearray)):
            try:
                decompressed = gzip.decompress(msg)
                text = decompressed.decode()
            except Exception:
                text = msg.decode()
        else:
            text = msg
        return json.loads(text)
    except Exception:
        return None


class HtxWS:
    def __init__(self, symbols: List[str], price_store, loop: asyncio.AbstractEventLoop,
                 exchange_name: str = "HTX", stagger_start: float = 0.0):
        """
        symbols: list like ["BTC-USDT", "ETH-USDT"]
        price_store: async PriceStore instance (has update and update_levels)
        loop: asyncio loop for run_coroutine_threadsafe
        """
        self.orig_symbols = symbols
        # huobi expects lowercase without dash
        self.tokens = [s.replace("-", "").lower() for s in symbols]
        self.symbol_map = {tok: orig for tok, orig in zip(self.tokens, symbols)}
        self.exchange = exchange_name
        self.price_store = price_store
        self.loop = loop
        self._stop = threading.Event()
        self._ws = None
        # local book: symbol -> {'bids': {price: size}, 'asks': {price: size}}
        self._local_books: Dict[str, Dict[str, Dict[float, float]]] = {s: {"bids": {}, "asks": {}} for s in symbols}
        
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
        """
        Apply list of [price, size] changes to local book side.
        size == 0 -> delete price level
        """
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
            
            # subscribe to ticker and depth.step0 for each token
            for tok in self.tokens:
                # ticker
                ws.send(json.dumps({"sub": f"market.{tok}.ticker"}))
                # depth snapshot/updates (step0 is full depth)
                ws.send(json.dumps({"sub": f"market.{tok}.depth.step0"}))
            logger.info(f"{self.exchange}: subscribed ticker+depth for {len(self.tokens)} symbols")
        except Exception:
            logger.exception("HTX on_open error")

    def _on_message(self, ws, msg):
        # Record message for health monitoring
        self._health_monitor.on_message_received()
        
        data = _safe_json_loads(msg)
        if not data:
            logger.debug("HTX: non-json or empty message")
            return
        logger.debug(f"HTX raw: {str(data)[:400]}")
        try:
            # application-level ping -> reply with pong
            if isinstance(data, dict) and "ping" in data:
                try:
                    ws.send(json.dumps({"pong": data["ping"]}))
                except Exception:
                    logger.exception("HTX send pong failed")
                return

            # Some Huobi/HTX messages are wrapped: {'ch':..., 'ts':..., 'tick': {...}}
            if isinstance(data, dict) and "tick" in data and isinstance(data["tick"], dict):
                ch = data.get("ch", "")
                tick = data["tick"]
                # Determine symbol from channel: "market.btcusdt.depth.step0" or "market.btcusdt.ticker"
                sym = None
                if isinstance(ch, str) and ch.startswith("market."):
                    parts = ch.split(".")
                    if len(parts) >= 2:
                        token = parts[1]
                        sym = self.symbol_map.get(token)

                # Depth snapshot/updates: tick may include 'bids' and 'asks' arrays
                bids = tick.get("bids")
                asks = tick.get("asks")
                if bids and asks and sym:
                    # bids: list of [price, qty] (best first or last - we will sort)
                    bids_levels = []
                    asks_levels = []
                    for p, s in bids[:DEPTH_LEVELS]:
                        try:
                            bids_levels.append((float(p), float(s)))
                        except Exception:
                            continue
                    for p, s in asks[:DEPTH_LEVELS]:
                        try:
                            asks_levels.append((float(p), float(s)))
                        except Exception:
                            continue
                    # replace local maps with snapshot-like data
                    bids_map = {p: s for p, s in bids_levels}
                    asks_map = {p: s for p, s in asks_levels}
                    self._local_books[sym]["bids"] = bids_map
                    self._local_books[sym]["asks"] = asks_map
                    bids_out = self._book_to_levels(self._local_books[sym]["bids"], "bids")
                    asks_out = self._book_to_levels(self._local_books[sym]["asks"], "asks")
                    logger.debug(f"HTX depth snapshot for {sym}: bids={len(bids_out)} asks={len(asks_out)}")
                    if bids_out and asks_out:
                        best_bid = bids_out[0][0] if bids_out else None
                        best_ask = asks_out[0][0] if asks_out else None
                        logger.debug(f"HTX -> update store: {sym} bid={best_bid} ask={best_ask}")
                    asyncio.run_coroutine_threadsafe(
                        self.price_store.update_levels(self.exchange, sym, bids_out, asks_out, time.time()),
                        self.loop
                    )
                    return

                # Some ticks include top-of-book fields (bid/ask/ bidSize/askSize/close)
                if "close" in tick and sym:
                    try:
                        close = float(tick["close"])
                    except Exception:
                        close = None
                    if close is not None:
                        # update top-of-book using close as both bid and ask fallback
                        logger.debug(f"HTX -> update store (ticker): {sym} close={close}")
                        asyncio.run_coroutine_threadsafe(
                            self.price_store.update(self.exchange, sym, close, None, close, None, time.time()),
                            self.loop
                        )
                        return

            # Some Huobi style messages may include a 'action' and 'data' fields for diffs.
            # Try to detect common incremental shapes:
            if isinstance(data, dict) and "depth" in data and isinstance(data["depth"], dict):
                # depth delta format (best-effort)
                depth = data["depth"]
                ch = data.get("ch", "")
                sym = None
                if ch and isinstance(ch, str) and ch.startswith("market."):
                    parts = ch.split(".")
                    if len(parts) >= 2:
                        token = parts[1]
                        sym = self.symbol_map.get(token)
                if not sym:
                    sym = data.get("symbol") or data.get("instrumentId")
                if sym:
                    # attempt to apply provided updates
                    bids_changes = depth.get("bids") or depth.get("bid") or []
                    asks_changes = depth.get("asks") or depth.get("ask") or []
                    if bids_changes:
                        self._apply_changes(sym, "bids", bids_changes)
                    if asks_changes:
                        self._apply_changes(sym, "asks", asks_changes)
                    bids_out = self._book_to_levels(self._local_books[sym]["bids"], "bids")
                    asks_out = self._book_to_levels(self._local_books[sym]["asks"], "asks")
                    if bids_out and asks_out:
                        best_bid = bids_out[0][0] if bids_out else None
                        best_ask = asks_out[0][0] if asks_out else None
                        logger.debug(f"HTX -> update store (delta): {sym} bid={best_bid} ask={best_ask}")
                    asyncio.run_coroutine_threadsafe(
                        self.price_store.update_levels(self.exchange, sym, bids_out, asks_out, time.time()),
                        self.loop
                    )
                    return

            # Fallback: sometimes messages are lists or other shapes — ignore safely
        except Exception:
            logger.exception("HTX processing error")

    def _on_error(self, ws, err):
        logger.warning(f"{self.exchange} WS error: {err}")

    def _on_close(self, ws, code, reason):
        logger.info(f"{self.exchange} WS closed: {code} {reason}")

    def _run(self):
        url = "wss://api.huobi.pro/ws"
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
                # disable control ping (use app-level ping/pong)
                ws.run_forever(ping_interval=None, ping_timeout=None)
                logger.warning(f"{self.exchange}: run_forever returned, will reconnect")
            except Exception:
                logger.exception("HTX run error - reconnecting")
            time.sleep(backoff + random.uniform(0, backoff * 0.2))
            backoff = min(backoff * 2, 60.0)

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