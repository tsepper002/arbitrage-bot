import time
import threading

# TODO: LEGACY FILE - This file is deprecated and will be removed in a future PR.
# Use core/price_store.py (PriceStore) as the canonical implementation.
# This file is kept temporarily to avoid breaking existing code.

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
