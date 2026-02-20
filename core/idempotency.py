"""
Idempotency Manager - Prevents duplicate trade execution
Ensures that operations are executed exactly once, even if requested multiple times.
"""

import asyncio
import hashlib
import logging
import time
from typing import Dict, Optional, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IdempotencyManager:
    """
    Manages idempotency keys to prevent duplicate operations.
    
    Features:
    - Request deduplication using idempotency keys
    - TTL-based automatic cleanup
    - SHA-256 key hashing
    - Thread-safe operations
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize idempotency manager.
        
        Args:
            ttl_seconds: Time-to-live for idempotency keys (default 1 hour)
        """
        self.ttl_seconds = ttl_seconds
        self.processed_keys: Dict[str, float] = {}  # key -> timestamp
        self.lock = asyncio.Lock()
        logger.info(f"IdempotencyManager initialized with TTL={ttl_seconds}s")
    
    def _generate_key(self, operation: str, params: dict) -> str:
        """
        Generate idempotency key from operation and parameters.
        
        Args:
            operation: Operation name (e.g., 'execute_trade')
            params: Operation parameters
        
        Returns:
            SHA-256 hash of operation + params
        """
        # Sort params for consistent hashing
        sorted_params = sorted(params.items())
        key_data = f"{operation}:{sorted_params}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    async def is_duplicate(self, operation: str, params: dict) -> bool:
        """
        Check if operation with given parameters was already processed.
        
        Args:
            operation: Operation name
            params: Operation parameters
        
        Returns:
            True if duplicate, False if new
        """
        key = self._generate_key(operation, params)
        
        async with self.lock:
            # Cleanup expired keys
            await self._cleanup_expired()
            
            # Check if key exists and not expired
            if key in self.processed_keys:
                timestamp = self.processed_keys[key]
                if time.time() - timestamp < self.ttl_seconds:
                    logger.warning(f"Duplicate operation detected: {operation}")
                    return True
                else:
                    # Expired, remove it
                    del self.processed_keys[key]
            
            return False
    
    async def mark_processed(self, operation: str, params: dict) -> str:
        """
        Mark operation as processed.
        
        Args:
            operation: Operation name
            params: Operation parameters
        
        Returns:
            Idempotency key
        """
        key = self._generate_key(operation, params)
        
        async with self.lock:
            self.processed_keys[key] = time.time()
            logger.debug(f"Marked operation as processed: {operation} (key={key[:16]}...)")
        
        return key
    
    async def _cleanup_expired(self):
        """Remove expired idempotency keys."""
        current_time = time.time()
        expired_keys = [
            k for k, t in self.processed_keys.items()
            if current_time - t >= self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self.processed_keys[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired idempotency keys")
    
    async def ensure_once(self, operation: str, params: dict):
        """
        Context manager to ensure operation executes exactly once.
        
        Usage:
            async with idempotency.ensure_once('execute_trade', trade_params):
                await execute_trade(trade_params)
        
        Args:
            operation: Operation name
            params: Operation parameters
        
        Raises:
            DuplicateOperationError: If operation already processed
        """
        if await self.is_duplicate(operation, params):
            raise DuplicateOperationError(
                f"Operation '{operation}' already processed with these parameters"
            )
        
        await self.mark_processed(operation, params)
    
    async def get_stats(self) -> dict:
        """
        Get idempotency manager statistics.
        
        Returns:
            Dictionary with stats
        """
        async with self.lock:
            await self._cleanup_expired()
            
            return {
                'active_keys': len(self.processed_keys),
                'ttl_seconds': self.ttl_seconds,
                'oldest_key_age': (
                    time.time() - min(self.processed_keys.values())
                    if self.processed_keys else 0
                )
            }
    
    async def clear_all(self):
        """Clear all idempotency keys (use with caution!)."""
        async with self.lock:
            count = len(self.processed_keys)
            self.processed_keys.clear()
            logger.warning(f"Cleared all {count} idempotency keys")
    
    async def remove_key(self, operation: str, params: dict) -> bool:
        """
        Manually remove specific idempotency key.
        
        Args:
            operation: Operation name
            params: Operation parameters
        
        Returns:
            True if key was removed, False if not found
        """
        key = self._generate_key(operation, params)
        
        async with self.lock:
            if key in self.processed_keys:
                del self.processed_keys[key]
                logger.info(f"Manually removed idempotency key: {operation}")
                return True
            return False


class DuplicateOperationError(Exception):
    """Raised when attempting to execute duplicate operation."""
    pass


# Global instance
_idempotency_manager: Optional[IdempotencyManager] = None


def get_idempotency_manager(ttl_seconds: int = 3600) -> IdempotencyManager:
    """
    Get global idempotency manager instance.
    
    Args:
        ttl_seconds: Time-to-live for idempotency keys
    
    Returns:
        IdempotencyManager instance
    """
    global _idempotency_manager
    
    if _idempotency_manager is None:
        _idempotency_manager = IdempotencyManager(ttl_seconds=ttl_seconds)
    
    return _idempotency_manager


# Usage example
"""
from core.idempotency import get_idempotency_manager, DuplicateOperationError

idempotency = get_idempotency_manager()

# Check before executing
trade_params = {'symbol': 'BTC/USDT', 'amount': 100, 'price': 50000}

if await idempotency.is_duplicate('execute_trade', trade_params):
    print("Trade already executed!")
else:
    # Execute trade
    await execute_trade(trade_params)
    await idempotency.mark_processed('execute_trade', trade_params)

# Or use context manager
try:
    async with idempotency.ensure_once('execute_trade', trade_params):
        await execute_trade(trade_params)
except DuplicateOperationError:
    print("Trade already executed!")

# Get statistics
stats = await idempotency.get_stats()
print(f"Active keys: {stats['active_keys']}")
"""
