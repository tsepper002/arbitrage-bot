"""Queue manager for task scheduling."""
import logging
from queue import PriorityQueue
from typing import Dict

logger = logging.getLogger(__name__)

class QueueManager:
    def __init__(self):
        self.queue = PriorityQueue()
        self.logger = logging.getLogger(__name__)
    
    def add_task(self, priority: int, task: Dict):
        self.queue.put((priority, task))
    
    def get_task(self) -> Dict:
        if not self.queue.empty():
            return self.queue.get()[1]
        return {}
    
    def size(self) -> int:
        return self.queue.qsize()
