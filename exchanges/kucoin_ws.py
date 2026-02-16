#!/usr/bin/env python3
"""
KuCoin single-connection WS client with depth (level2) subscription and delta apply logic.
- keeps a local book (price->size) per symbol
- applies snapshots and incremental changes (if provided)
- publishes top-DEPTH_LEVELS to PriceStore via update_levels
- deduplicates 'ack' messages to avoid log spam
Enhanced with health monitoring and reconnection support.
"""
import json
import threading
import time
import logging
from typing import List, Optional, Tuple, Dict
import requests
import websocket
import asyncio
import random
from .ws_helpers import WSHealthMonitor, WSReconnectHelper

logger = logging.getLogger("kucoin_ws")
# Logging configured in main.py - don't override here

DEPTH_LEVELS = 20

def _safe_json_loads(msg) -> Optional[dict]:
    try:
        if isinstance(msg, (bytes, bytearray)):
            return json.loads(msg.decode())
        return json.loads(msg)
    except Exception:
        return None

class KucoinWS:
    def __init__(self, symbols: List[str], price_store, loop: asyncio.AbstractEventLoop,
                 exchange_name: str = "KuCoin", stagger_start: float = 0.0):
        self.orig_symbols = symbols
        self.symbols = symbols
        self.exchange = exchange_name
        self.price_store = price_store
        self.loop = loop
        self._stop = threading.Event()
        self._ws = None
        # local book: map symbol -> dict price->size for bids and asks
        self._local_books: Dict[str, Dict[str, Dict[float, float]]] = {sym: {"bids": {}, "asks": {}} for sym in symbols}
        # seen ack ids to deduplicate ack logs and processing
        self._seen_acks: set = set()
        
        # Add health monitoring
        self._health_monitor = WSHealthMonitor(exchange_name)
        self._reconnect_helper = WSReconnectHelper(exchange_name)
        self._stopping = False  # Flag to prevent reconnects during shutdown
        
        self._thread = threading.Thread(target=self._run, daemon=True)
        if stagger_start and stagger_start > 0:
            time.sleep(stagger_start * random.uniform(0.5, 1.5))
        self._thread.start()

    def _prepare_endpoint(self) -> Optional[str]:
        try:
            r = requests.post("https://api.kucoin.com/api/v1/bullet-public", timeout=5)
            r.raise_for_status()
            data = r.json()
            token = data["data"]["token"]
            endpoint = data["data"]["instanceServers"][0]["endpoint"]
            return f"{endpoint}?token={token}"
        except Exception:
            logger.exception("KuCoin token fetch error")
            return None

    def _book_to_levels(self, book_side: Dict[float, float], side: str) -> List[Tuple[float, float]]:
        items = list(book_side.items())
        if side == "bids":
            items_sorted = sorted(items, key=lambda x: -x[0])[:DEPTH_LEVELS]
        else:
            items_sorted = sorted(items, key=lambda x: x[0])[:DEPTH_LEVELS]
        return [(float(p), float(s)) for p, s in items_sorted]

    def _apply_changes(self, sym: str, side: str, changes: List[List[str]]):
        """
        changes: list of [price, size] — if size == '0' -> delete
        side: 'bids' or 'asks'
        """
        book = self._local_books.get(sym)
        if book is None:
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
            
            for sym in self.symbols:
                topic_ticker = f"/market/ticker:{sym}"
                sub_ticker = {"id": int(time.time()), "type": "subscribe", "topic": topic_ticker, "privateChannel": False, "response": True}
                ws.send(json.dumps(sub_ticker))
                topic_lvl2 = f"/market/level2:{sym}"
                sub_lvl2 = {"id": int(time.time()) + 1, "type": "subscribe", "topic": topic_lvl2, "privateChannel": False, "response": True}
                ws.send(json.dumps(sub_lvl2))
            logger.info(f"{self.exchange}: subscribed ticker+level2 for {len(self.symbols)} symbols")
        except Exception:
            logger.exception("KuCoin on_open error")

    def _on_message(self, ws, msg):
        # Record message for health monitoring
        self._health_monitor.on_message_received()
        
        data = _safe_json_loads(msg)
        if not data:
            logger.debug("KuCoin: non-json or empty message")
            return

        # Deduplicate and quietly ignore repeated 'ack' messages to avoid spam.
        # Log the first time we see an ack id (for debug), ignore duplicates.
        if isinstance(data, dict) and data.get("type") == "ack":
            ack_id = data.get("id")
            if ack_id is None:
                # generic ack without id — ignore
                return
            if ack_id in self._seen_acks:
                return
            # first time seeing this ack id — remember and log once
            self._seen_acks.add(ack_id)
            logger.debug(f"KuCoin ack received for id={ack_id}")
            return

        logger.debug(f"KuCoin raw: {str(data)[:400]}")
        try:
            if data.get("type") == "message" and isinstance(data.get("data"), dict):
                topic = data.get("topic", "")
                payload = data.get("data", {})

                # snapshot style with bids/asks arrays
                if "bids" in payload and "asks" in payload:
                    # full snapshot: replace local book entries
                    sym = None
                    if ":" in topic:
                        _, sym = topic.split(":", 1)
                    if not sym:
                        sym = payload.get("symbol") or payload.get("symbolName")
                    if not sym:
                        return
                    # set maps
                    bids_map = {}
                    asks_map = {}
                    for p_s in payload.get("bids", []):
                        try:
                            p = float(p_s[0]); s = float(p_s[1])
                            if s > 0:
                                bids_map[p] = s
                        except Exception:
                            continue
                    for p_s in payload.get("asks", []):
                        try:
                            p = float(p_s[0]); s = float(p_s[1])
                            if s > 0:
                                asks_map[p] = s
                        except Exception:
                            continue
                    self._local_books[sym]["bids"] = bids_map
                    self._local_books[sym]["asks"] = asks_map
                    bids_levels = self._book_to_levels(self._local_books[sym]["bids"], "bids")
                    asks_levels = self._book_to_levels(self._local_books[sym]["asks"], "asks")
                    logger.debug(f"KuCoin depth snapshot for {sym}: bids={len(bids_levels)} asks={len(asks_levels)}")
                    
                    # Track symbol-level health
                    self._health_monitor.on_message_received(sym)
                    
                    asyncio.run_coroutine_threadsafe(
                        self.price_store.update_levels(self.exchange, sym, bids_levels, asks_levels, time.time()),
                        self.loop
                    )
                    return

                # incremental updates: some formats use 'changes' or 'delta' fields
                # try to detect common shapes
                sym = None
                if ":" in topic:
                    _, sym = topic.split(":", 1)
                if not sym:
                    sym = payload.get("symbol") or payload.get("symbolName")

                # try 'changes' structure
                if "changes" in payload and isinstance(payload["changes"], dict):
                    ch = payload["changes"]
                    if "bids" in ch:
                        self._apply_changes(sym, "bids", ch["bids"])
                    if "asks" in ch:
                        self._apply_changes(sym, "asks", ch["asks"])
                    bids_levels = self._book_to_levels(self._local_books[sym]["bids"], "bids")
                    asks_levels = self._book_to_levels(self._local_books[sym]["asks"], "asks")
                    asyncio.run_coroutine_threadsafe(
                        self.price_store.update_levels(self.exchange, sym, bids_levels, asks_levels, time.time()),
                        self.loop
                    )
                    return

                # some updates may come with 'bids'/'asks' fields directly (treat as changes)
                if "bids" in payload or "asks" in payload:
                    if "bids" in payload:
                        self._apply_changes(sym, "bids", payload.get("bids", []))
                    if "asks" in payload:
                        self._apply_changes(sym, "asks", payload.get("asks", []))
                    bids_levels = self._book_to_levels(self._local_books[sym]["bids"], "bids")
                    asks_levels = self._book_to_levels(self._local_books[sym]["asks"], "asks")
                    asyncio.run_coroutine_threadsafe(
                        self.price_store.update_levels(self.exchange, sym, bids_levels, asks_levels, time.time()),
                        self.loop
                    )
                    return

                # ticker fallback: update top-of-book
                if data.get("topic", "").startswith("/market/ticker:"):
                    topic = data.get("topic", "")
                    sym = None
                    if ":" in topic:
                        _, sym = topic.split(":", 1)
                    payload = data.get("data", {})
                    def _to_float(x):
                        try:
                            return float(x) if x is not None else None
                        except Exception:
                            return None
                    best_ask = _to_float(payload.get("bestAsk"))
                    best_ask_size = _to_float(payload.get("bestAskSize"))
                    best_bid = _to_float(payload.get("bestBid"))
                    best_bid_size = _to_float(payload.get("bestBidSize"))
                    price = _to_float(payload.get("price"))
                    ask = best_ask or price
                    bid = best_bid or price
                    ask_size = best_ask_size
                    bid_size = best_bid_size
                    if sym:
                        logger.debug(f"KuCoin -> update store: {sym} bid={bid} ask={ask} bid_size={bid_size} ask_size={ask_size}")
                        asyncio.run_coroutine_threadsafe(
                            self.price_store.update(self.exchange, sym, bid, bid_size, ask, ask_size, time.time()),
                            self.loop
                        )
        except Exception:
            logger.exception("KuCoin processing error")

    def _on_error(self, ws, err):
        logger.warning(f"{self.exchange} WS error: {err}")

    def _on_close(self, ws, code, reason):
        logger.info(f"{self.exchange} WS closed: {code} {reason}")
        if self._stopping:
            logger.info(f"{self.exchange} WebSocket stopped gracefully")

    def _run(self):
        backoff = 1.0
        while not self._stop.is_set():
            # Check if we're stopping
            if self._stopping:
                logger.info(f"{self.exchange}: Stopping, no reconnect")
                break
                
            endpoint = self._prepare_endpoint()
            if not endpoint:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                continue
            try:
                logger.info(f"{self.exchange}: connecting to {endpoint}")
                ws = websocket.WebSocketApp(
                    endpoint,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws = ws
                ws.run_forever(ping_interval=20, ping_timeout=10)
                logger.warning(f"{self.exchange}: run_forever returned, will reconnect")
            except Exception as e:
                logger.exception(f"KuCoin run error - reconnecting: {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60.0)

    def stop(self):
        self._stopping = True  # Prevent reconnect attempts during shutdown
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