"""
Message Queue - Async task processing for distributed arbitrage operations.

This module provides a message queue system for asynchronous task processing,
enabling decoupled architecture and handling high-volume task distribution.

Features:
- Asynchronous task queuing and processing
- Multiple priority levels
- Task retry with exponential backoff
- Dead letter queue for failed tasks
- Worker pool management
- Task result tracking

Expected Impact: Async processing, decoupled architecture
"""

import asyncio
import logging
import time
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from collections import deque
import hashlib

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class Task:
    """Represents a task in the queue."""
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    error: Optional[str] = None
    result: Optional[Any] = None
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class MessageQueue:
    """
    Message queue for asynchronous task processing.
    
    Manages task queuing, distribution to workers, retry logic,
    and result tracking for distributed arbitrage operations.
    """
    
    def __init__(self, num_workers: int = 4):
        """
        Initialize message queue.
        
        Args:
            num_workers: Number of worker tasks to process queue
        """
        self.num_workers = num_workers
        
        # Separate queues for each priority level
        self.queues: Dict[TaskPriority, deque] = {
            priority: deque() for priority in TaskPriority
        }
        
        self.tasks: Dict[str, Task] = {}
        self.task_handlers: Dict[str, Callable] = {}
        self.dead_letter_queue: List[Task] = []
        
        self.workers: List[asyncio.Task] = []
        self.running = False
        
        # Statistics
        self.stats = {
            'total_enqueued': 0,
            'total_processed': 0,
            'total_failed': 0,
            'total_retried': 0
        }
        
        logger.info(f"MessageQueue initialized with {num_workers} workers")
    
    def register_handler(self, task_type: str, handler: Callable):
        """
        Register a handler function for a task type.
        
        Args:
            task_type: Type of task to handle
            handler: Async function to process the task
        """
        self.task_handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")
    
    def generate_task_id(self, task_type: str, payload: Dict) -> str:
        """
        Generate unique task ID based on type and payload.
        
        Args:
            task_type: Type of task
            payload: Task payload
            
        Returns:
            Unique task ID
        """
        data = f"{task_type}:{json.dumps(payload, sort_keys=True)}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    async def enqueue(self, 
                     task_type: str, 
                     payload: Dict[str, Any],
                     priority: TaskPriority = TaskPriority.NORMAL,
                     max_retries: int = 3) -> str:
        """
        Add a task to the queue.
        
        Args:
            task_type: Type of task
            payload: Task data
            priority: Task priority level
            max_retries: Maximum retry attempts
            
        Returns:
            Task ID
        """
        task_id = self.generate_task_id(task_type, payload)
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries
        )
        
        self.queues[priority].append(task)
        self.tasks[task_id] = task
        self.stats['total_enqueued'] += 1
        
        logger.debug(f"Enqueued task {task_id} (type={task_type}, priority={priority.name})")
        
        return task_id
    
    async def dequeue(self) -> Optional[Task]:
        """
        Get next task from queue (highest priority first).
        
        Returns:
            Next task to process or None
        """
        # Check queues in priority order (highest first)
        for priority in sorted(TaskPriority, key=lambda p: p.value, reverse=True):
            if self.queues[priority]:
                task = self.queues[priority].popleft()
                task.status = TaskStatus.PROCESSING
                task.started_at = time.time()
                return task
        
        return None
    
    async def process_task(self, task: Task) -> bool:
        """
        Process a single task.
        
        Args:
            task: Task to process
            
        Returns:
            True if successful
        """
        try:
            # Get handler for this task type
            handler = self.task_handlers.get(task.task_type)
            
            if not handler:
                raise ValueError(f"No handler registered for task type: {task.task_type}")
            
            # Execute handler
            logger.debug(f"Processing task {task.task_id} (type={task.task_type})")
            result = await handler(task.payload)
            
            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.result = result
            
            self.stats['total_processed'] += 1
            
            logger.info(f"Task {task.task_id} completed successfully "
                       f"(duration={task.completed_at - task.started_at:.2f}s)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {e}")
            
            task.error = str(e)
            task.retry_count += 1
            
            # Retry logic
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRY
                
                # Exponential backoff
                delay = 2 ** task.retry_count
                await asyncio.sleep(delay)
                
                # Re-queue with lower priority
                self.queues[TaskPriority.LOW].append(task)
                self.stats['total_retried'] += 1
                
                logger.info(f"Task {task.task_id} will be retried "
                          f"(attempt {task.retry_count}/{task.max_retries})")
            else:
                # Move to dead letter queue
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()
                self.dead_letter_queue.append(task)
                self.stats['total_failed'] += 1
                
                logger.error(f"Task {task.task_id} failed after {task.max_retries} retries")
            
            return False
    
    async def worker(self, worker_id: int):
        """
        Worker coroutine that processes tasks from queue.
        
        Args:
            worker_id: Worker identifier
        """
        logger.info(f"Worker {worker_id} started")
        
        while self.running:
            try:
                # Get next task
                task = await self.dequeue()
                
                if task:
                    await self.process_task(task)
                else:
                    # No tasks available, wait a bit
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def start(self):
        """Start the message queue and workers."""
        if self.running:
            logger.warning("MessageQueue already running")
            return
        
        self.running = True
        
        # Start worker tasks
        for i in range(self.num_workers):
            worker_task = asyncio.create_task(self.worker(i))
            self.workers.append(worker_task)
        
        logger.info(f"MessageQueue started with {self.num_workers} workers")
    
    async def stop(self):
        """Stop the message queue and workers."""
        if not self.running:
            return
        
        logger.info("Stopping MessageQueue...")
        self.running = False
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        
        self.workers.clear()
        logger.info("MessageQueue stopped")
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        Get status of a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task status dictionary or None
        """
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return {
            'task_id': task.task_id,
            'task_type': task.task_type,
            'status': task.status.value,
            'priority': task.priority.name,
            'created_at': task.created_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
            'retry_count': task.retry_count,
            'error': task.error,
            'result': task.result
        }
    
    def get_queue_stats(self) -> Dict:
        """
        Get queue statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            'queue_sizes': {
                priority.name: len(self.queues[priority])
                for priority in TaskPriority
            },
            'total_queue_size': sum(len(q) for q in self.queues.values()),
            'dead_letter_queue_size': len(self.dead_letter_queue),
            'num_workers': self.num_workers,
            'running': self.running,
            'statistics': self.stats.copy()
        }


# Global instance
_queue: Optional[MessageQueue] = None


def get_message_queue(num_workers: int = 4) -> MessageQueue:
    """
    Get or create global message queue instance.
    
    Args:
        num_workers: Number of worker tasks
        
    Returns:
        MessageQueue instance
    """
    global _queue
    if _queue is None:
        _queue = MessageQueue(num_workers)
    return _queue
