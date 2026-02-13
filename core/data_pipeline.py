"""Data pipeline for ETL operations."""
import logging

logger = logging.getLogger(__name__)

class DataPipeline:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.stages = []
    
    def add_stage(self, transform_func):
        self.stages.append(transform_func)
    
    def process(self, data):
        result = data
        for stage in self.stages:
            result = stage(result)
        return result
    
    def extract(self, source):
        self.logger.info(f"Extracting from {source}")
        return []
    
    def transform(self, data):
        # Clean and transform
        return [d for d in data if d is not None]
    
    def load(self, data, destination):
        self.logger.info(f"Loading to {destination}: {len(data)} records")
