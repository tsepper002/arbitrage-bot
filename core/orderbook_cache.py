"""
Order Book Caching Module
Implements LRU cache with TTL for orderbook data to reduce API calls and improve performance.
"""
import asyncio
import time
from collections import OrderedDict
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with data and timestamp"""
    data: Any
    timestamp: float
    hits: int = 0


class OrderbookCache:
    """
    LRU Cache with TTL for orderbook data.
    
    Features:
    - LRU (Least Recently Used) eviction
    - TTL (Time To Live) for entries
    - Per-symbol, per-exchange caching
    - Statistics tracking
    """
    
    def __init__(self, max_size: int = 1000, ttl_ms: float = 100):
        """
        Initialize orderbook cache.
        
        Args:
            max_size: Maximum number of entries
            ttl_ms: Time to live in milliseconds
        """
        self.max_size = max_size
        self.ttl_ms = ttl_ms
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expired': 0
        }
        self._lock = asyncio.Lock()
    
    def _make_key(self, symbol: str, exchange: str) -> str:
        """Create cache key from symbol and exchange"""
        return f"{exchange}:{symbol}"
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if cache entry is expired"""
        age_ms = (time.time() - entry.timestamp) * 1000
        return age_ms > self.ttl_ms
    
    async def get(self, symbol: str, exchange: str) -> Optional[Dict]:
        """
        Get orderbook from cache.
        
        Args:
            symbol: Trading pair symbol
            exchange: Exchange name
            
        Returns:
            Cached orderbook or None if not found/expired
        """
        async with self._lock:
            key = self._make_key(symbol, exchange)
            
            if key not in self.cache:
                self.stats['misses'] += 1
                return None
            
            entry = self.cache[key]
            
            # Check if expired
            if self._is_expired(entry):
                del self.cache[key]
                self.stats['expired'] += 1
                self.stats['misses'] += 1
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            entry.hits += 1
            self.stats['hits'] += 1
            
            return entry.data
    
    async def set(self, symbol: str, exchange: str, data: Dict) -> None:
        """
        Store orderbook in cache.
        
        Args:
            symbol: Trading pair symbol
            exchange: Exchange name
            data: Orderbook data to cache
        """
        async with self._lock:
            key = self._make_key(symbol, exchange)
            
            # Remove if already exists
            if key in self.cache:
                del self.cache[key]
            
            # Add new entry
            self.cache[key] = CacheEntry(
                data=data,
                timestamp=time.time(),
                hits=0
            )
            
            # Evict oldest if over size limit
            while len(self.cache) > self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                self.stats['evictions'] += 1
    
    async def invalidate(self, symbol: str = None, exchange: str = None) -> None:
        """
        Invalidate cache entries.
        
        Args:
            symbol: Symbol to invalidate (None = all)
            exchange: Exchange to invalidate (None = all)
        """
        async with self._lock:
            if symbol is None and exchange is None:
                self.cache.clear()
            else:
                keys_to_remove = []
                for key in self.cache:
                    ex, sym = key.split(':', 1)
                    if (exchange is None or ex == exchange) and \
                       (symbol is None or sym == symbol):
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    del self.cache[key]
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'ttl_ms': self.ttl_ms,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': f"{hit_rate:.2f}%",
            'evictions': self.stats['evictions'],
            'expired': self.stats['expired']
        }
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns number removed."""
        async with self._lock:
            keys_to_remove = []
            for key, entry in self.cache.items():
                if self._is_expired(entry):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.cache[key]
                self.stats['expired'] += 1
            
            return len(keys_to_remove)


# Global cache instance
_cache_instance: Optional[OrderbookCache] = None


def get_orderbook_cache(max_size: int = 1000, ttl_ms: float = 100) -> OrderbookCache:
    """
    Get global orderbook cache instance.
    
    Args:
        max_size: Maximum cache size
        ttl_ms: TTL in milliseconds
        
    Returns:
        OrderbookCache instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = OrderbookCache(max_size=max_size, ttl_ms=ttl_ms)
    return _cache_instance
