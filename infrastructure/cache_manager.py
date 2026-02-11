"""Cache Manager - Multi-level caching system"""
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self.l1_cache = {}  # In-memory cache
        self.cache_stats = {'hits': 0, 'misses': 0}
        
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self.l1_cache:
            entry = self.l1_cache[key]
            if datetime.now() < entry['expires']:
                self.cache_stats['hits'] += 1
                return entry['value']
            else:
                del self.l1_cache[key]
        
        self.cache_stats['misses'] += 1
        return None
        
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        ttl = ttl or self.default_ttl
        self.l1_cache[key] = {
            'value': value,
            'expires': datetime.now() + timedelta(seconds=ttl)
        }
        
    def delete(self, key: str):
        """Delete from cache"""
        if key in self.l1_cache:
            del self.l1_cache[key]
            
    def clear(self):
        """Clear all cache"""
        self.l1_cache.clear()
        logger.info("Cache cleared")
        
    def cleanup_expired(self):
        """Remove expired entries"""
        now = datetime.now()
        expired = [k for k, v in self.l1_cache.items() if now >= v['expires']]
        for key in expired:
            del self.l1_cache[key]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired entries")
            
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            'size': len(self.l1_cache),
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'hit_rate': hit_rate
        }
