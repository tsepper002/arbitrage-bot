"""
Visualization Engine - Data visualization and charting
Generates visual representations of trading data
"""
import logging
from typing import Dict, List
import time

logger = logging.getLogger(__name__)

class VisualizationEngine:
    """Generates visualizations for trading data"""
    
    def __init__(self):
        self.charts = {}
        logger.info("✅ VisualizationEngine initialized")
    
    def create_pnl_chart(self, pnl_data: List[Dict]) -> Dict:
        """Create P&L chart"""
        try:
            chart_data = {
                'type': 'line',
                'title': 'Profit & Loss Over Time',
                'x_label': 'Time',
                'y_label': 'P&L (USD)',
                'data_points': len(pnl_data),
                'created': time.time()
            }
            
            self.charts['pnl'] = chart_data
            logger.info(f"Created P&L chart with {len(pnl_data)} points")
            return chart_data
            
        except Exception as e:
            logger.error(f"Error creating P&L chart: {e}")
            return {}
    
    def create_trade_distribution(self, trades: List[Dict]) -> Dict:
        """Create trade distribution chart"""
        try:
            # Count trades by exchange/symbol
            distribution = {}
            for trade in trades:
                key = trade.get('exchange', 'unknown')
                distribution[key] = distribution.get(key, 0) + 1
            
            chart_data = {
                'type': 'bar',
                'title': 'Trade Distribution',
                'data': distribution,
                'created': time.time()
            }
            
            self.charts['distribution'] = chart_data
            logger.info("Created trade distribution chart")
            return chart_data
            
        except Exception as e:
            logger.error(f"Error creating distribution chart: {e}")
            return {}
    
    def create_performance_heatmap(self, performance_by_symbol: Dict) -> Dict:
        """Create performance heatmap"""
        try:
            chart_data = {
                'type': 'heatmap',
                'title': 'Performance by Symbol',
                'data': performance_by_symbol,
                'created': time.time()
            }
            
            self.charts['heatmap'] = chart_data
            logger.info("Created performance heatmap")
            return chart_data
            
        except Exception as e:
            logger.error(f"Error creating heatmap: {e}")
            return {}

def get_visualization_engine():
    """Factory function"""
    return VisualizationEngine()
