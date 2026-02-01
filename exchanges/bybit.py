import asyncio
import json
import websockets
import time

class Bybit:
    def __init__(self, store, symbols):
        self.store = store
        self.symbols = symbols
        self.last = {}

    async def run(self):
        url = "wss://stream.bybit.com/v5/public/spot"
        async with websockets.connect(url) as ws:
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
                self.store.update("BYBIT", s, bid, ask)
