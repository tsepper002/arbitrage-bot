"""
Cross-Margining Manager
Manages portfolio margin and capital efficiency across positions
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class CrossMarginingManager:
    """Manages cross-margining and portfolio margin"""
    
    def __init__(self):
        self.positions = {}
        self.margin_requirements = {}
        self.correlation_matrix = {}
        
    async def calculate_portfolio_margin(self, positions: List[Dict]) -> Dict:
        """
        Calculate portfolio margin requirement
        
        Args:
            positions: List of position data
            
        Returns:
            Margin calculation results
        """
        try:
            if not positions:
                return self._create_empty_margin_result()
            
            total_initial_margin = 0
            total_maintenance_margin = 0
            net_liquidation_value = 0
            
            # Calculate individual position margins
            for position in positions:
                pos_margin = self._calculate_position_margin(position)
                total_initial_margin += pos_margin['initial']
                total_maintenance_margin += pos_margin['maintenance']
                net_liquidation_value += position.get('value', 0)
            
            # Apply portfolio margin offset (risk reduction from diversification)
            offset = self._calculate_margin_offset(positions)
            portfolio_margin = total_initial_margin * (1 - offset)
            
            # Calculate margin utilization
            available_margin = net_liquidation_value - portfolio_margin
            utilization = (portfolio_margin / net_liquidation_value * 100) if net_liquidation_value > 0 else 0
            
            return {
                'timestamp': datetime.now().isoformat(),
                'portfolio_margin': portfolio_margin,
                'individual_margin': total_initial_margin,
                'margin_offset': offset * 100,  # percentage
                'margin_saved': total_initial_margin - portfolio_margin,
                'available_margin': available_margin,
                'margin_utilization': utilization,
                'net_liquidation_value': net_liquidation_value,
                'positions_count': len(positions)
            }
            
        except Exception as e:
            logger.error(f"Error calculating portfolio margin: {e}")
            return self._create_empty_margin_result()
    
    def _calculate_position_margin(self, position: Dict) -> Dict:
        """Calculate margin for a single position"""
        size = abs(position.get('size', 0))
        price = position.get('price', 0)
        leverage = position.get('leverage', 1)
        
        notional_value = size * price
        
        # Standard margin requirements
        initial_margin_rate = 1 / leverage if leverage > 0 else 1.0
        maintenance_margin_rate = initial_margin_rate * 0.5
        
        return {
            'initial': notional_value * initial_margin_rate,
            'maintenance': notional_value * maintenance_margin_rate
        }
    
    def _calculate_margin_offset(self, positions: List[Dict]) -> float:
        """
        Calculate margin offset from portfolio diversification
        
        Args:
            positions: List of positions
            
        Returns:
            Offset percentage (0.0 to 1.0)
        """
        if len(positions) < 2:
            return 0.0
        
        # Calculate correlation between positions
        avg_correlation = self._calculate_average_correlation(positions)
        
        # More diversification (lower correlation) = higher offset
        # Correlation of 1.0 = 0% offset
        # Correlation of 0.0 = 30% offset
        # Correlation of -1.0 = 50% offset
        
        if avg_correlation >= 0:
            offset = 0.3 * (1 - avg_correlation)
        else:
            offset = 0.3 + 0.2 * abs(avg_correlation)
        
        return min(offset, 0.5)  # Cap at 50% offset
    
    def _calculate_average_correlation(self, positions: List[Dict]) -> float:
        """Calculate average correlation between positions"""
        # In production, would calculate actual price correlations
        # For now, using mock correlation based on symbols
        
        if len(positions) < 2:
            return 1.0
        
        correlations = []
        for i, pos1 in enumerate(positions):
            for pos2 in positions[i+1:]:
                corr = self._get_correlation(pos1.get('symbol'), pos2.get('symbol'))
                correlations.append(corr)
        
        return sum(correlations) / len(correlations) if correlations else 1.0
    
    def _get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Get correlation between two symbols"""
        # Mock correlation data
        # In production, would calculate from historical prices
        
        if symbol1 == symbol2:
            return 1.0
        
        # BTC-related pairs tend to correlate
        btc_related = ['BTC', 'ETH']
        if any(x in symbol1 for x in btc_related) and any(x in symbol2 for x in btc_related):
            return 0.7
        
        return 0.3  # Default low correlation
    
    def _create_empty_margin_result(self) -> Dict:
        """Create empty margin calculation result"""
        return {
            'portfolio_margin': 0,
            'individual_margin': 0,
            'margin_offset': 0,
            'margin_saved': 0,
            'available_margin': 0,
            'margin_utilization': 0,
            'timestamp': datetime.now().isoformat()
        }
    
    async def optimize_capital_efficiency(self, positions: List[Dict], total_capital: float) -> Dict:
        """
        Optimize capital efficiency across positions
        
        Args:
            positions: Current positions
            total_capital: Total available capital
            
        Returns:
            Optimization results
        """
        try:
            margin_result = await self.calculate_portfolio_margin(positions)
            
            required_margin = margin_result['portfolio_margin']
            available_for_new = total_capital - required_margin
            
            # Calculate capital efficiency metrics
            capital_in_use = sum(abs(p.get('size', 0) * p.get('price', 0)) for p in positions)
            
            efficiency_ratio = (capital_in_use / total_capital * 100) if total_capital > 0 else 0
            
            return {
                'timestamp': datetime.now().isoformat(),
                'total_capital': total_capital,
                'margin_required': required_margin,
                'capital_available': available_for_new,
                'capital_in_use': capital_in_use,
                'efficiency_ratio': efficiency_ratio,
                'margin_utilization': margin_result['margin_utilization'],
                'can_add_positions': available_for_new > (total_capital * 0.1),  # Keep 10% buffer
                'recommendations': self._generate_efficiency_recommendations(
                    efficiency_ratio,
                    margin_result['margin_utilization']
                )
            }
            
        except Exception as e:
            logger.error(f"Error optimizing capital efficiency: {e}")
            return {}
    
    def _generate_efficiency_recommendations(self, efficiency: float, utilization: float) -> List[str]:
        """Generate capital efficiency recommendations"""
        recommendations = []
        
        if efficiency < 50:
            recommendations.append("Low capital efficiency - consider increasing position sizes")
        elif efficiency > 90:
            recommendations.append("Very high capital efficiency - consider risk management")
        
        if utilization < 30:
            recommendations.append("Low margin utilization - opportunity to add positions")
        elif utilization > 70:
            recommendations.append("High margin utilization - reduce risk or add capital")
        
        if not recommendations:
            recommendations.append("Capital efficiency is optimal")
        
        return recommendations
    
    def get_margining_stats(self) -> Dict:
        """Get cross-margining statistics"""
        return {
            'active_positions': len(self.positions),
            'tracked_margins': len(self.margin_requirements),
            'last_update': datetime.now().isoformat()
        }
