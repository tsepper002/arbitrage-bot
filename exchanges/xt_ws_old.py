import json
import threading
import websocket

class XtWS:
    def __init__(self, symbol: str):
        self.symbol = symbol.replace("-", "_")
        self.price = None
        self._start()

    def _on_message(self, ws, message):
        if not message or message == "ping":
            return
        try:
            data = json.loads(message)
            if "result" in data and "last" in data["result"]:
                self.price = float(data["result"]["last"])
        except:
            pass

    def _on_open(self, ws):
        ws.send(json.dumps({
            "method": "subscribe",
            "params": {
                "channel": "ticker",
                "symbol": self.symbol
            }
        }))

    def _start(self):
        def run():
            websocket.WebSocketApp(
                "wss://stream.xt.com/public",
                on_open=self._on_open,
                on_message=self._on_message
            ).run_forever()
        threading.Thread(target=run, daemon=True).start()

    async def get_price(self, _):
        return self.price
