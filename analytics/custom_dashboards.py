"""Custom dashboard builder."""
import logging

logger = logging.getLogger(__name__)

class DashboardBuilder:
    def __init__(self):
        self.widgets = []
        self.logger = logging.getLogger(__name__)
    
    def add_widget(self, widget_type, data):
        self.widgets.append({'type': widget_type, 'data': data})
    
    def render(self):
        self.logger.info(f"Rendering dashboard with {len(self.widgets)} widgets")
        return {'widgets': self.widgets}
