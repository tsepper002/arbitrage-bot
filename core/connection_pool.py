"""
Connection Pooling Module
Manages HTTP connection pools for efficient connection reuse across API calls.
"""
import asyncio
import aiohttp
from typing import Dict, Optional
from collections import defaultdict
import time
import logging

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    HTTP Connection Pool Manager.
    
    Features:
    - Reuses HTTP connections
    - Per-exchange pools
    - Connection health checks
    - Automatic cleanup
    """
    
    def __init__(
        self,
        min_pool_size: int = 5,
        max_pool_size: int = 50,
        timeout_seconds: float = 30,
        keepalive_timeout: float = 60
    ):
        """
        Initialize connection pool.
        
        Args:
            min_pool_size: Minimum connections per pool
            max_pool_size: Maximum connections per pool
            timeout_seconds: Request timeout
            keepalive_timeout: Connection keepalive timeout
        """
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.timeout_seconds = timeout_seconds
        self.keepalive_timeout = keepalive_timeout
        
        self.pools: Dict[str, aiohttp.ClientSession] = {}
        self.stats = defaultdict(lambda: {
            'requests': 0,
            'errors': 0,
            'connections_created': 0
        })
        self._lock = asyncio.Lock()
    
    async def get_session(self, exchange: str) -> aiohttp.ClientSession:
        """
        Get or create a session for an exchange.
        
        Args:
            exchange: Exchange name
            
        Returns:
            ClientSession for the exchange
        """
        async with self._lock:
            if exchange not in self.pools:
                connector = aiohttp.TCPConnector(
                    limit=self.max_pool_size,
                    limit_per_host=self.max_pool_size,
                    ttl_dns_cache=300,
                    keepalive_timeout=self.keepalive_timeout,
                    enable_cleanup_closed=True
                )
                
                timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
                
                self.pools[exchange] = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers={
                        'User-Agent': 'ArbitrageBot/1.0',
                        'Connection': 'keep-alive'
                    }
                )
                
                self.stats[exchange]['connections_created'] += 1
                logger.info(f"Created connection pool for {exchange}")
            
            return self.pools[exchange]
    
    async def request(
        self,
        exchange: str,
        method: str,
        url: str,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        Make HTTP request using pooled connection.
        
        Args:
            exchange: Exchange name
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters
            
        Returns:
            Response object
        """
        session = await self.get_session(exchange)
        
        try:
            self.stats[exchange]['requests'] += 1
            response = await session.request(method, url, **kwargs)
            return response
        except Exception as e:
            self.stats[exchange]['errors'] += 1
            logger.error(f"Request error for {exchange}: {e}")
            raise
    
    async def get(self, exchange: str, url: str, **kwargs):
        """Make GET request"""
        return await self.request(exchange, 'GET', url, **kwargs)
    
    async def post(self, exchange: str, url: str, **kwargs):
        """Make POST request"""
        return await self.request(exchange, 'POST', url, **kwargs)
    
    async def close_pool(self, exchange: str):
        """Close connection pool for an exchange"""
        async with self._lock:
            if exchange in self.pools:
                await self.pools[exchange].close()
                del self.pools[exchange]
                logger.info(f"Closed connection pool for {exchange}")
    
    async def close_all(self):
        """Close all connection pools"""
        async with self._lock:
            for exchange, session in list(self.pools.items()):
                await session.close()
            self.pools.clear()
            logger.info("Closed all connection pools")
    
    def get_stats(self) -> Dict:
        """Get connection pool statistics"""
        return {
            'pools': len(self.pools),
            'by_exchange': dict(self.stats)
        }
    
    async def health_check(self, exchange: str) -> bool:
        """
        Check if connection pool for exchange is healthy.
        
        Args:
            exchange: Exchange name
            
        Returns:
            True if healthy, False otherwise
        """
        try:
            if exchange not in self.pools:
                return False
            
            session = self.pools[exchange]
            return not session.closed
        except Exception as e:
            logger.error(f"Health check failed for {exchange}: {e}")
            return False


# Global pool instance
_pool_instance: Optional[ConnectionPool] = None


def get_connection_pool(
    min_pool_size: int = 5,
    max_pool_size: int = 50
) -> ConnectionPool:
    """
    Get global connection pool instance.
    
    Args:
        min_pool_size: Minimum pool size
        max_pool_size: Maximum pool size
        
    Returns:
        ConnectionPool instance
    """
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = ConnectionPool(
            min_pool_size=min_pool_size,
            max_pool_size=max_pool_size
        )
    return _pool_instance
