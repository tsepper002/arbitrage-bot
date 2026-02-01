import asyncio
import json
import websockets
import time
import logging
from typing import List

logger = logging.getLogger("bybit")

# TODO: LEGACY FILE - This is a legacy implementation.
# Use exchanges/bybit_ws.py (BybitWS) for production.
# This file is kept temporarily for reference.

class Bybit:
    def __init__(self, symbols: List[str], store, loop: asyncio.AbstractEventLoop = None, 
                 exchange_name: str = "Bybit", stagger_start: float = 0.0):
        self.store = store
        self.symbols = symbols
        self.last = {}
        self.exchange_name = exchange_name
        self.loop = loop or asyncio.get_event_loop()

    async def run(self):
        url = "wss://stream.bybit.com/v5/public/spot"
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(url) as ws:
                    logger.info(f"{self.exchange_name}: connected to {url}")
                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": [f"orderbook.1.{s}" for s in self.symbols]
                    }))

                    while True:
                        msg = json.loads(await ws.recv())
                        data = msg.get("data")
                        if not data:
                            continue

                        s = data["s"]
                        bid = float(data["b"][0][0])
                        ask = float(data["a"][0][0])

                        now = time.time()
                        if now - self.last.get(s, 0) < 0.5:
                            continue

                        self.last[s] = now
                        # FIX: Use await for async store.update
                        await self.store.update(self.exchange_name, s, bid, None, ask, None, now)
            except asyncio.CancelledError:
                logger.info(f"{self.exchange_name}: cancelled")
                break
            except Exception as e:
                logger.error(f"{self.exchange_name}: error - {e}, reconnecting in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
    
    def stop(self):
        # Placeholder for stop method - implement if needed
        pass
