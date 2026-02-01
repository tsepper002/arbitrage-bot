# arbitrage_bot/exchanges/mexc.py
import asyncio
import json
import websockets
import logging
import time
from typing import List

log = logging.getLogger("MEXC")

# TODO: LEGACY FILE - This is a legacy implementation.
# Use exchanges/mexc_ws.py (MexcWS) for production.
# This file is kept temporarily for reference.

class MEXC:
    WS_URL = "wss://wbs.mexc.com/ws"

    def __init__(self, symbols: List[str], store, loop: asyncio.AbstractEventLoop = None,
                 exchange_name: str = "MEXC", stagger_start: float = 0.0):
        self.store = store
        self.symbols = symbols
        self.exchange_name = exchange_name
        self.loop = loop or asyncio.get_event_loop()

    async def run(self):
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(self.WS_URL, ping_interval=20) as ws:
                    log.info(f"{self.exchange_name}: WS connected")

                    for s in self.symbols:
                        msg = {
                            "method": "SUBSCRIPTION",
                            "params": [f"spot@public.limit.depth.v3.api@{s}@1"],
                        }
                        await ws.send(json.dumps(msg))

                    async for raw in ws:
                        data = json.loads(raw)

                        if "d" not in data:
                            continue

                        symbol = data["s"]
                        bids = data["d"].get("bids")
                        asks = data["d"].get("asks")

                        if not bids or not asks:
                            continue

                        bid = float(bids[0][0])
                        ask = float(asks[0][0])
                        bid_size = float(bids[0][1]) if len(bids[0]) > 1 else None
                        ask_size = float(asks[0][1]) if len(asks[0]) > 1 else None

                        # FIX: Use await for async store.update
                        await self.store.update(self.exchange_name, symbol, bid, bid_size, ask, ask_size, time.time())

            except asyncio.CancelledError:
                log.info(f"{self.exchange_name}: cancelled")
                break
            except Exception as e:
                log.warning(f"{self.exchange_name}: reconnecting: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
    
    def stop(self):
        # Placeholder for stop method - implement if needed
        pass
