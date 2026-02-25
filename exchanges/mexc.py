# arbitrage_bot/exchanges/mexc.py
"""
MEXC exchange WebSocket + REST fallback for orderbook data.

MEXC migrated to wss://wbs-api.mexc.com/ws (Aug 2025) and
switched public market streams to Protocol Buffers (protobuf).
Since protobuf decoding adds complexity, we use a REST polling
fallback: GET /api/v3/depth?symbol=X&limit=5 every 1-2 seconds.

This gives reliable JSON data with ~1s latency — sufficient for
arbitrage on a $20 account where trade frequency is low.
"""
import asyncio
import json
import time
import logging

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import websockets
    HAS_WS = True
except ImportError:
    HAS_WS = False

log = logging.getLogger("MEXC")

class MEXC:
    # New endpoint (Aug 2025 migration)
    WS_URL = "wss://wbs-api.mexc.com/ws"
    WS_URL_LEGACY = "wss://wbs.mexc.com/ws"
    REST_URL = "https://api.mexc.com/api/v3/depth"
    REST_POLL_INTERVAL = 1.5  # seconds between REST polls

    def __init__(self, store, symbols):
        self.store = store
        self.symbols = symbols
        self._mexc_symbols = [s.replace("-", "") for s in symbols]
        self._sym_map = {s.replace("-", ""): s for s in symbols}
        self._stop = False
        self._backoff = 1.0
        self._max_backoff = 60.0
        self._last_msg_time = 0
        self._data_received = False  # Track if we ever got valid data
        self._ws_failed = False  # Track if WS is broken (triggers REST fallback)

    def stop(self):
        self._stop = True

    async def run(self):
        """Main entry: REST polling (reliable JSON).

        MEXC migrated public market streams to protobuf (Aug 2025).
        The WS connects but sends binary frames that we can't parse,
        while subscription confirmations are JSON (so protobuf detection
        never triggers). REST polling gives reliable JSON at ~1.5s latency,
        which is fine since MEXC has 0% spot trading fees.
        """
        if HAS_AIOHTTP:
            try:
                log.info("MEXC: using aiohttp REST polling (0% fees, reliable JSON data)")
                await self._run_rest_poll()
            except Exception as e:
                log.warning(f"MEXC: aiohttp REST failed ({type(e).__name__}: {e}), falling back to urllib")
                await self._run_rest_poll_stdlib()
        else:
            log.info("MEXC: using urllib REST polling (aiohttp not installed)")
            await self._run_rest_poll_stdlib()

    async def _run_ws(self, url: str):
        """Try WebSocket connection. Exits after 10s with no data (protobuf detection)."""
        try:
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                log.info(f"MEXC WS connected to {url}")
                self._backoff = 1.0
                self._last_msg_time = time.time()

                for s in self._mexc_symbols:
                    msg = {
                        "method": "SUBSCRIPTION",
                        "params": [f"spot@public.limit.depth.v3.api@{s}@5"],
                    }
                    await ws.send(json.dumps(msg))

                json_msg_count = 0
                binary_msg_count = 0

                async for raw in ws:
                    if self._stop:
                        break

                    self._last_msg_time = time.time()

                    # Detect protobuf: binary frames can't be JSON-parsed
                    if isinstance(raw, bytes):
                        binary_msg_count += 1
                        if binary_msg_count >= 3 and json_msg_count == 0:
                            log.warning(f"MEXC WS sends protobuf (binary), switching to REST")
                            return  # Exit WS, let run() fall back to REST
                        continue

                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        binary_msg_count += 1
                        if binary_msg_count >= 3 and json_msg_count == 0:
                            log.warning(f"MEXC WS sends non-JSON data, switching to REST")
                            return
                        continue

                    json_msg_count += 1

                    # Parse depth data
                    mexc_symbol, bids, asks = self._parse_ws_message(data)
                    if not mexc_symbol or not bids or not asks:
                        continue

                    levels = self._parse_levels(bids, asks)
                    if not levels:
                        continue

                    bids_levels, asks_levels = levels
                    std_symbol = self._sym_map.get(mexc_symbol, mexc_symbol)
                    await self.store.update_levels("MEXC", std_symbol, bids_levels, asks_levels, time.time())
                    self._data_received = True

        except Exception as e:
            log.warning(f"MEXC WS error on {url}: {type(e).__name__}: {e}")
            raise

    def _parse_ws_message(self, data: dict):
        """Extract symbol, bids, asks from MEXC WS JSON message."""
        mexc_symbol = ""
        bids = None
        asks = None

        if "d" in data:
            mexc_symbol = data.get("s", "")
            if not mexc_symbol and "c" in data:
                parts = data["c"].split("@")
                if len(parts) >= 3:
                    mexc_symbol = parts[2]
            inner = data["d"]
            if isinstance(inner, dict):
                bids = inner.get("bids")
                asks = inner.get("asks")
        elif "bids" in data or "asks" in data:
            mexc_symbol = data.get("symbol", "") or data.get("s", "")
            if not mexc_symbol and "c" in data:
                parts = data["c"].split("@")
                if len(parts) >= 3:
                    mexc_symbol = parts[2]
            bids = data.get("bids")
            asks = data.get("asks")

        return mexc_symbol, bids, asks

    def _parse_levels(self, bids, asks):
        """Parse bid/ask levels from MEXC format (dict, array, or string array)."""
        try:
            sample = bids[0]
            if isinstance(sample, dict):
                bids_levels = [(float(b["p"]), float(b["v"])) for b in bids]
                asks_levels = [(float(a["p"]), float(a["v"])) for a in asks]
            else:
                bids_levels = [(float(b[0]), float(b[1])) for b in bids]
                asks_levels = [(float(a[0]), float(a[1])) for a in asks]
            return bids_levels, asks_levels
        except (ValueError, IndexError, TypeError, KeyError) as e:
            log.debug(f"MEXC parse error: {e}")
            return None

    async def _run_rest_poll(self):
        """Poll MEXC REST API for orderbook data every 1.5 seconds using aiohttp."""
        log.info(f"MEXC aiohttp REST polling started for {len(self._mexc_symbols)} symbols")
        consecutive_errors = 0
        async with aiohttp.ClientSession() as session:
            while not self._stop:
                success_count = 0
                for mexc_sym in self._mexc_symbols:
                    if self._stop:
                        break
                    try:
                        url = f"{self.REST_URL}?symbol={mexc_sym}&limit=5"
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                bids_raw = data.get("bids", [])
                                asks_raw = data.get("asks", [])
                                if bids_raw and asks_raw:
                                    bids_levels = [(float(b[0]), float(b[1])) for b in bids_raw]
                                    asks_levels = [(float(a[0]), float(a[1])) for a in asks_raw]
                                    std_symbol = self._sym_map.get(mexc_sym, mexc_sym)
                                    await self.store.update_levels("MEXC", std_symbol, bids_levels, asks_levels, time.time())
                                    success_count += 1
                            elif resp.status == 429:
                                log.warning(f"MEXC REST rate-limited, pausing 2s")
                                await asyncio.sleep(2.0)
                            else:
                                log.debug(f"MEXC REST {mexc_sym}: HTTP {resp.status}")
                    except Exception as e:
                        if consecutive_errors < 3:
                            log.warning(f"MEXC REST {mexc_sym}: {type(e).__name__}: {e}")
                        else:
                            log.debug(f"MEXC REST {mexc_sym}: {type(e).__name__}: {e}")
                    await asyncio.sleep(0.1)

                if success_count > 0:
                    if not self._data_received:
                        log.info(f"✅ MEXC: Connected via REST ({success_count}/{len(self._mexc_symbols)} symbols)")
                        self._data_received = True
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    if consecutive_errors <= 3:
                        log.warning(f"MEXC REST: 0/{len(self._mexc_symbols)} symbols succeeded (attempt {consecutive_errors})")

                await asyncio.sleep(self.REST_POLL_INTERVAL)

    async def _run_rest_poll_stdlib(self):
        """Fallback REST polling using stdlib urllib (no extra packages needed)."""
        import urllib.request
        log.info(f"MEXC stdlib REST polling started for {len(self._mexc_symbols)} symbols")
        consecutive_errors = 0
        while not self._stop:
            success_count = 0
            for mexc_sym in self._mexc_symbols:
                if self._stop:
                    break
                try:
                    url = f"{self.REST_URL}?symbol={mexc_sym}&limit=5"
                    loop = asyncio.get_running_loop()
                    resp_bytes = await loop.run_in_executor(
                        None,
                        lambda u=url: urllib.request.urlopen(
                            urllib.request.Request(u, headers={"User-Agent": "arbitrage-bot/1.0"}),
                            timeout=5
                        ).read()
                    )
                    data = json.loads(resp_bytes)
                    bids_raw = data.get("bids", [])
                    asks_raw = data.get("asks", [])
                    if bids_raw and asks_raw:
                        bids_levels = [(float(b[0]), float(b[1])) for b in bids_raw]
                        asks_levels = [(float(a[0]), float(a[1])) for a in asks_raw]
                        std_symbol = self._sym_map.get(mexc_sym, mexc_sym)
                        await self.store.update_levels("MEXC", std_symbol, bids_levels, asks_levels, time.time())
                        success_count += 1
                except Exception as e:
                    if consecutive_errors < 3:
                        log.warning(f"MEXC REST {mexc_sym}: {type(e).__name__}: {e}")
                    else:
                        log.debug(f"MEXC REST {mexc_sym}: {type(e).__name__}: {e}")
                await asyncio.sleep(0.1)

            if success_count > 0:
                if not self._data_received:
                    log.info(f"✅ MEXC: Connected via REST ({success_count}/{len(self._mexc_symbols)} symbols)")
                    self._data_received = True
                consecutive_errors = 0
            else:
                consecutive_errors += 1
                if consecutive_errors <= 3:
                    log.warning(f"MEXC REST: 0/{len(self._mexc_symbols)} symbols succeeded (attempt {consecutive_errors})")

            await asyncio.sleep(self.REST_POLL_INTERVAL)
