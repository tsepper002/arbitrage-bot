"""Performance optimizer."""
import logging
import time

logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.timings = {}
    
    def profile_function(self, func, *args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        
        func_name = func.__name__
        if func_name not in self.timings:
            self.timings[func_name] = []
        self.timings[func_name].append(elapsed)
        
        return result
    
    def get_bottlenecks(self):
        bottlenecks = []
        for func, times in self.timings.items():
            avg_time = sum(times) / len(times)
            if avg_time > 0.1:  # >100ms
                bottlenecks.append({'function': func, 'avg_time': avg_time})
        return sorted(bottlenecks, key=lambda x: x['avg_time'], reverse=True)
