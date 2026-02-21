# arbitrage_bot/exchanges/mexc.py
import asyncio
import json
import time
import websockets
import logging

log = logging.getLogger("MEXC")

class MEXC:
    WS_URL = "wss://wbs.mexc.com/ws"

    def __init__(self, store, symbols):
        self.store = store
        # Original symbols in standard format (e.g., BTC-USDT)
        self.symbols = symbols
        # MEXC API uses no-separator format (e.g., BTCUSDT)
        self._mexc_symbols = [s.replace("-", "") for s in symbols]
        # Reverse mapping: BTCUSDT -> BTC-USDT for PriceStore
        self._sym_map = {s.replace("-", ""): s for s in symbols}
        self._stop = False
        self._backoff = 1.0  # Start with 1s backoff
        self._max_backoff = 60.0
        self._last_msg_time = 0

    def stop(self):
        self._stop = True

    async def run(self):
        while not self._stop:
            try:
                async with websockets.connect(
                    self.WS_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    log.info("MEXC WS connected")
                    self._backoff = 1.0  # Reset backoff on successful connect
                    self._last_msg_time = time.time()

                    for s in self._mexc_symbols:
                        # @5 = 5 levels of depth (more stable than @1 which drops on thin books)
                        msg = {
                            "method": "SUBSCRIPTION",
                            "params": [f"spot@public.limit.depth.v3.api@{s}@5"],
                        }
                        await ws.send(json.dumps(msg))

                    async for raw in ws:
                        if self._stop:
                            break
                        
                        self._last_msg_time = time.time()
                        data = json.loads(raw)

                        # MEXC v3 API: data can be nested under "d" or flat at top level
                        # Try nested format first ({"s": ..., "d": {"bids": ..., "asks": ...}})
                        # then flat format ({"symbol": ..., "bids": ..., "asks": ...})
                        if "d" in data:
                            mexc_symbol = data.get("s", "")
                            # Fallback: extract symbol from channel name "c"
                            # e.g. "spot@public.limit.depth.v3.api@BTCUSDT@5" → "BTCUSDT"
                            if not mexc_symbol and "c" in data:
                                parts = data["c"].split("@")
                                if len(parts) >= 3:
                                    mexc_symbol = parts[2]
                            bids = data["d"].get("bids")
                            asks = data["d"].get("asks")
                        elif "bids" in data or "asks" in data:
                            mexc_symbol = data.get("symbol", "") or data.get("s", "")
                            bids = data.get("bids")
                            asks = data.get("asks")
                        else:
                            continue

                        if not bids or not asks:
                            continue

                        try:
                            ts = time.time()
                            # MEXC sends depth entries as {"p": price, "v": volume} dicts,
                            # as [price, volume] arrays, or as ["price", "qty"] string arrays
                            sample = bids[0]
                            if isinstance(sample, dict):
                                bids_levels = [(float(b["p"]), float(b["v"])) for b in bids]
                                asks_levels = [(float(a["p"]), float(a["v"])) for a in asks]
                            else:
                                bids_levels = [(float(b[0]), float(b[1])) for b in bids]
                                asks_levels = [(float(a[0]), float(a[1])) for a in asks]
                        except (ValueError, IndexError, TypeError, KeyError):
                            continue

                        # Convert MEXC symbol (BTCUSDT) back to standard format (BTC-USDT)
                        std_symbol = self._sym_map.get(mexc_symbol, mexc_symbol)
                        await self.store.update_levels("MEXC", std_symbol, bids_levels, asks_levels, ts)

            except websockets.exceptions.ConnectionClosedError as e:
                log.warning(f"MEXC WS closed: {e.code} {e.reason}")
            except Exception as e:
                log.warning(f"MEXC reconnecting ({self._backoff:.0f}s): {type(e).__name__}: {e}")
            
            if not self._stop:
                await asyncio.sleep(self._backoff)
                self._backoff = min(self._backoff * 1.5, self._max_backoff)
