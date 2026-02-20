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
        self.symbols = symbols
        self._stop = False

    def stop(self):
        self._stop = True

    async def run(self):
        while not self._stop:
            try:
                async with websockets.connect(self.WS_URL, ping_interval=20) as ws:
                    log.info("MEXC WS connected")

                    for s in self.symbols:
                        msg = {
                            "method": "SUBSCRIPTION",
                            "params": [f"spot@public.limit.depth.v3.api@{s}@1"],
                        }
                        await ws.send(json.dumps(msg))

                    async for raw in ws:
                        if self._stop:
                            break
                        data = json.loads(raw)

                        if "d" not in data:
                            continue

                        symbol = data["s"]
                        bids = data["d"].get("bids")
                        asks = data["d"].get("asks")

                        if not bids or not asks:
                            continue

                        try:
                            ts = time.time()
                            bids_levels = [(float(b[0]), float(b[1])) for b in bids]
                            asks_levels = [(float(a[0]), float(a[1])) for a in asks]
                        except (ValueError, IndexError, TypeError):
                            continue

                        await self.store.update_levels("MEXC", symbol, bids_levels, asks_levels, ts)

            except Exception as e:
                log.warning(f"MEXC reconnecting: {e}")
                if not self._stop:
                    await asyncio.sleep(3)
