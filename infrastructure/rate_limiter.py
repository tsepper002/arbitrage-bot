"""Rate limiter using token bucket."""
import time
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.logger = logging.getLogger(__name__)
    
    def acquire(self) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
