"""
Request Batching Module
Batches multiple API requests together to reduce network overhead and improve throughput.
"""
import asyncio
import time
from collections import defaultdict
from typing import Dict, List, Callable, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class BatchedRequest:
    """Represents a request waiting to be batched"""
    request_id: str
    endpoint: str
    params: Dict[str, Any]
    timestamp: float
    future: asyncio.Future = field(default_factory=asyncio.Future)


class RequestBatcher:
    """
    Batches API requests to reduce network overhead.
    
    Features:
    - Collects requests over a time window
    - Batches by endpoint
    - Automatic flush on timeout
    - Configurable batch sizes
    """
    
    def __init__(
        self,
        batch_window_ms: float = 50,
        max_batch_size: int = 100,
        max_wait_ms: float = 200
    ):
        """
        Initialize request batcher.
        
        Args:
            batch_window_ms: Collection window in milliseconds
            max_batch_size: Maximum requests per batch
            max_wait_ms: Maximum wait time before forcing flush
        """
        self.batch_window_ms = batch_window_ms
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        
        self.pending: Dict[str, List[BatchedRequest]] = defaultdict(list)
        self.batch_handlers: Dict[str, Callable] = {}
        self.stats = {
            'total_requests': 0,
            'batches_sent': 0,
            'requests_batched': 0
        }
        
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start the batcher background task"""
        if not self._running:
            self._running = True
            self._flush_task = asyncio.create_task(self._flush_loop())
            logger.info("Request batcher started")
    
    async def stop(self):
        """Stop the batcher and flush pending requests"""
        self._running = False
        if self._flush_task:
            await self._flush_pending()
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        logger.info("Request batcher stopped")
    
    def register_handler(self, endpoint: str, handler: Callable):
        """
        Register a batch handler for an endpoint.
        
        Args:
            endpoint: API endpoint name
            handler: Async function that processes a batch
        """
        self.batch_handlers[endpoint] = handler
        logger.info(f"Registered batch handler for {endpoint}")
    
    async def add_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> Any:
        """
        Add request to batch queue.
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            request_id: Optional request ID
            
        Returns:
            Response from the batched request
        """
        if endpoint not in self.batch_handlers:
            raise ValueError(f"No handler registered for endpoint: {endpoint}")
        
        if request_id is None:
            request_id = f"{endpoint}_{time.time()}_{id(params)}"
        
        request = BatchedRequest(
            request_id=request_id,
            endpoint=endpoint,
            params=params,
            timestamp=time.time()
        )
        
        async with self._lock:
            self.pending[endpoint].append(request)
            self.stats['total_requests'] += 1
            
            # Check if we should flush immediately
            if len(self.pending[endpoint]) >= self.max_batch_size:
                await self._flush_endpoint(endpoint)
        
        # Wait for result
        return await request.future
    
    async def _flush_loop(self):
        """Background task to periodically flush batches"""
        while self._running:
            try:
                await asyncio.sleep(self.batch_window_ms / 1000)
                await self._flush_pending()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")
    
    async def _flush_pending(self):
        """Flush all pending requests"""
        async with self._lock:
            endpoints = list(self.pending.keys())
        
        for endpoint in endpoints:
            try:
                await self._flush_endpoint(endpoint)
            except Exception as e:
                logger.error(f"Error flushing {endpoint}: {e}")
    
    async def _flush_endpoint(self, endpoint: str):
        """Flush pending requests for a specific endpoint"""
        async with self._lock:
            if endpoint not in self.pending or not self.pending[endpoint]:
                return
            
            batch = self.pending[endpoint][:]
            self.pending[endpoint] = []
        
        if not batch:
            return
        
        # Check for stale requests
        now = time.time()
        current_batch = []
        stale_requests = []
        
        for req in batch:
            age_ms = (now - req.timestamp) * 1000
            if age_ms > self.max_wait_ms:
                stale_requests.append(req)
            else:
                current_batch.append(req)
        
        # Handle stale requests
        for req in stale_requests:
            req.future.set_exception(
                TimeoutError(f"Request waited too long: {age_ms:.0f}ms")
            )
        
        if not current_batch:
            return
        
        # Execute batch
        handler = self.batch_handlers[endpoint]
        
        try:
            # Extract params for batch
            batch_params = [req.params for req in current_batch]
            
            # Execute batch handler
            results = await handler(batch_params)
            
            # Distribute results
            if len(results) != len(current_batch):
                raise ValueError(
                    f"Handler returned {len(results)} results for "
                    f"{len(current_batch)} requests"
                )
            
            for req, result in zip(current_batch, results):
                if not req.future.done():
                    req.future.set_result(result)
            
            self.stats['batches_sent'] += 1
            self.stats['requests_batched'] += len(current_batch)
            
        except Exception as e:
            logger.error(f"Error executing batch for {endpoint}: {e}")
            for req in current_batch:
                if not req.future.done():
                    req.future.set_exception(e)
    
    def get_stats(self) -> Dict:
        """Get batching statistics"""
        avg_batch_size = (
            self.stats['requests_batched'] / self.stats['batches_sent']
            if self.stats['batches_sent'] > 0 else 0
        )
        
        return {
            'total_requests': self.stats['total_requests'],
            'batches_sent': self.stats['batches_sent'],
            'requests_batched': self.stats['requests_batched'],
            'avg_batch_size': f"{avg_batch_size:.2f}",
            'pending_by_endpoint': {
                ep: len(reqs) for ep, reqs in self.pending.items()
            }
        }


# Global batcher instance
_batcher_instance: Optional[RequestBatcher] = None


def get_request_batcher(
    batch_window_ms: float = 50,
    max_batch_size: int = 100
) -> RequestBatcher:
    """
    Get global request batcher instance.
    
    Args:
        batch_window_ms: Batch collection window
        max_batch_size: Maximum batch size
        
    Returns:
        RequestBatcher instance
    """
    global _batcher_instance
    if _batcher_instance is None:
        _batcher_instance = RequestBatcher(
            batch_window_ms=batch_window_ms,
            max_batch_size=max_batch_size
        )
    return _batcher_instance
