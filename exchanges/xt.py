import asyncio
import json
import logging
import websockets

log = logging.getLogger("XT")


class XT:
    def __init__(self, store, symbols):
        self.store = store
        self.symbols = symbols
        self.url = "wss://stream.xt.com/public"

    async def run(self):
        while True:
            try:
                async with websockets.connect(self.url) as ws:
                    log.info("XT WS connected")

                    for s in self.symbols:
                        await ws.send(json.dumps({
                            "method": "subscribe",
                            "params": [f"ticker@{s.lower()}"],
                            "id": 1
                        }))

                    while True:
                        raw = await ws.recv()
                        if not raw:
                            continue

                        msg = json.loads(raw)

                        data = msg.get("data")
                        if not data:
                            continue

                        bid = float(data.get("bid", 0))
                        ask = float(data.get("ask", 0))
                        symbol = data.get("symbol", "").upper()

                        if bid and ask:
                            self.store.update("XT", symbol, bid, ask)

            except Exception as e:
                log.warning(f"XT reconnecting: {e}")
                await asyncio.sleep(2)
