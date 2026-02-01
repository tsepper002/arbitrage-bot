# arbitrage_bot/exchanges/mexc.py
import asyncio
import json
import websockets
import logging

log = logging.getLogger("MEXC")

class MEXC:
    WS_URL = "wss://wbs.mexc.com/ws"

    def __init__(self, store, symbols):
        self.store = store
        self.symbols = symbols

    async def run(self):
        while True:
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

                        self.store.update("MEXC", symbol, bid, ask)

            except Exception as e:
                log.warning(f"MEXC reconnecting: {e}")
                await asyncio.sleep(3)
