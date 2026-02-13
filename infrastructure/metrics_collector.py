"""Metrics collector for monitoring."""
import logging
from typing import Dict
from collections import defaultdict

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self):
        self.metrics = defaultdict(list)
        self.logger = logging.getLogger(__name__)
    
    def record(self, name: str, value: float):
        self.metrics[name].append(value)
    
    def get_avg(self, name: str) -> float:
        values = self.metrics.get(name, [])
        return sum(values) / len(values) if values else 0.0
    
    def export_prometheus(self) -> str:
        lines = []
        for name, values in self.metrics.items():
            avg = sum(values) / len(values) if values else 0
            lines.append(f'{name} {avg}')
        return '
'.join(lines)
