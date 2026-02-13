"""Data validator for input validation."""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DataValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate(self, data: Dict, schema: Dict) -> bool:
        for key, type_expected in schema.items():
            if key not in data:
                return False
            if not isinstance(data[key], type_expected):
                return False
        return True
    
    def clean(self, data: Dict) -> Dict:
        cleaned = {}
        for key, value in data.items():
            if value is not None:
                cleaned[key] = value
        return cleaned
