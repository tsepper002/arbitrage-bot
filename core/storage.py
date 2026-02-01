import time
import threading


class PriceStorage:
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()

    def update(self, exchange, pair, bid, ask):
        with self.lock:
            self.data.setdefault(exchange, {})
            self.data[exchange][pair] = {
                "bid": bid,
                "ask": ask,
                "ts": time.time()
            }

    def get(self, exchange, pair):
        return self.data.get(exchange, {}).get(pair)
