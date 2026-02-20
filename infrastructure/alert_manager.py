"""Alert manager for notifications."""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self):
        self.alerts = []
        self.logger = logging.getLogger(__name__)
    
    def send_alert(self, level: str, message: str, channels: List[str] = None):
        alert = {'level': level, 'message': message, 'channels': channels or ['log']}
        self.alerts.append(alert)
        self.logger.warning(f"{level}: {message}")
    
    def get_alerts(self) -> List[Dict]:
        return self.alerts
