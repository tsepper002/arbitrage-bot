"""Turbo-charged price store with multi-level caching."""
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class PriceStoreTurbo:
    """High-performance price store with caching."""
    
    def __init__(self, l1_ttl=1, l2_ttl=5):
        self.l1_cache = {}  # Fast cache
        self.l2_cache = {}  # Slower but larger
        self.l1_ttl = l1_ttl
        self.l2_ttl = l2_ttl
        self.stats = {'l1_hits': 0, 'l2_hits': 0, 'misses': 0}
        self.logger = logging.getLogger(__name__)
    
    def get(self, key: str) -> Optional[Dict]:
        """Get price with multi-level caching."""
        now = time.time()
        
        # Check L1 cache
        if key in self.l1_cache:
            data, timestamp = self.l1_cache[key]
            if now - timestamp < self.l1_ttl:
                self.stats['l1_hits'] += 1
                return data
        
        # Check L2 cache
        if key in self.l2_cache:
            data, timestamp = self.l2_cache[key]
            if now - timestamp < self.l2_ttl:
                self.stats['l2_hits'] += 1
                self.l1_cache[key] = (data, now)  # Promote to L1
                return data
        
        self.stats['misses'] += 1
        return None
    
    def set(self, key: str, data: Dict):
        """Set price in all cache levels."""
        now = time.time()
        self.l1_cache[key] = (data, now)
        self.l2_cache[key] = (data, now)
    
    def cleanup(self):
        """Remove expired entries."""
        now = time.time()
        self.l1_cache = {k: v for k, v in self.l1_cache.items() 
                         if now - v[1] < self.l1_ttl}
        self.l2_cache = {k: v for k, v in self.l2_cache.items() 
                         if now - v[1] < self.l2_ttl}
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = sum(self.stats.values())
        return {
            'l1_hit_rate': self.stats['l1_hits'] / total if total > 0 else 0,
            'l2_hit_rate': self.stats['l2_hits'] / total if total > 0 else 0,
            **self.stats
        }
