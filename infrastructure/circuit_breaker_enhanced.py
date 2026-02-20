"""Enhanced circuit breaker pattern."""
import time
import logging

logger = logging.getLogger(__name__)

class CircuitBreakerEnhanced:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = 'closed'
        self.logger = logging.getLogger(__name__)
    
    def call(self, func, *args, **kwargs):
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'half_open'
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            if self.state == 'half_open':
                self.state = 'closed'
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                self.state = 'open'
            raise e
