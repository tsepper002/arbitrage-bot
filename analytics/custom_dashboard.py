"""
Custom Dashboard - Unified analytics dashboard
Provides real-time view of all trading metrics
"""
import logging
from typing import Dict, List
import time

logger = logging.getLogger(__name__)

class CustomDashboard:
    """Unified analytics dashboard"""
    
    def __init__(self):
        self.widgets = {}
        self.metrics = {}
        self.refresh_interval = 5  # seconds
        logger.info("✅ CustomDashboard initialized")
    
    def add_widget(self, widget_id: str, widget_type: str, data_source: callable):
        """Add widget to dashboard"""
        self.widgets[widget_id] = {
            'type': widget_type,
            'data_source': data_source,
            'last_update': 0
        }
        logger.info(f"Added dashboard widget: {widget_id} ({widget_type})")
    
    def get_dashboard_data(self) -> Dict:
        """Get all dashboard data"""
        try:
            dashboard_data = {
                'timestamp': time.time(),
                'widgets': {}
            }
            
            for widget_id, widget in self.widgets.items():
                try:
                    # Get data from source
                    data = widget['data_source']()
                    dashboard_data['widgets'][widget_id] = {
                        'type': widget['type'],
                        'data': data,
                        'updated': time.time()
                    }
                except Exception as e:
                    logger.error(f"Error getting data for widget {widget_id}: {e}")
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {}
    
    def render(self) -> str:
        """Render dashboard as text"""
        try:
            data = self.get_dashboard_data()
            output = ["\n" + "="*80]
            output.append("TRADING DASHBOARD")
            output.append("="*80)
            
            for widget_id, widget_data in data.get('widgets', {}).items():
                output.append(f"\n[{widget_id.upper()}] ({widget_data['type']})")
                output.append(str(widget_data['data']))
            
            output.append("="*80 + "\n")
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Error rendering dashboard: {e}")
            return "Dashboard error"

def get_custom_dashboard():
    """Factory function"""
    return CustomDashboard()
