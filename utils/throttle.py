# arbitrage_bot/utils/throttle.py
import time

class Throttle:
    def __init__(self, interval=0.3):
        self.interval = interval
        self.last = {}

    def allow(self, key):
        now = time.time()
        if now - self.last.get(key, 0) >= self.interval:
            self.last[key] = now
            return True
        return False
