import asyncio
import json
import websockets
import logging

class HTX:
    def __init__(self, store):
        self.store = store
        self.url = "wss://api.huobi.pro/ws"

    async def run(self):
        while True:  # ← ВАЖНО: бесконечный цикл
            try:
                async with websockets.connect(self.url, ping_interval=20) as ws:
                    logging.info("HTX WS connected")

                    # подписка
                    for symbol in ["btcusdt", "ethusdt", "solusdt"]:
                        sub = {
                            "sub": f"market.{symbol}.ticker",
                            "id": symbol
                        }
                        await ws.send(json.dumps(sub))

                    while True:
                        raw = await ws.recv()
                        data = json.loads(raw)

                        if "tick" not in data:
                            continue

                        symbol = data["ch"].split(".")[1].upper()
                        price = float(data["tick"]["close"])

                        self.store.update("HTX", symbol, price)

            except Exception as e:
                logging.warning(f"HTX reconnecting: {e}")
                await asyncio.sleep(2)
