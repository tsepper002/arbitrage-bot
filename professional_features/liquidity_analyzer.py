"""
Liquidity Analyzer - Analyzes market liquidity
Calculates liquidity metrics and depth analysis
"""
import logging
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

class LiquidityAnalyzer:
    """Analyzes orderbook liquidity"""
    
    def __init__(self):
        self.liquidity_history = {}
        logger.info("✅ LiquidityAnalyzer initialized")
    
    def analyze(self, symbol: str, orderbook: Dict) -> Dict:
        """Analyze liquidity for symbol"""
        try:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            if not bids or not asks:
                return {
                    'sufficient_liquidity': False,
                    'bid_liquidity': 0,
                    'ask_liquidity': 0,
                    'total_liquidity': 0,
                    'spread_bps': 0
                }
            
            # Calculate liquidity metrics
            bid_liquidity = self._calculate_depth(bids, depth_levels=10)
            ask_liquidity = self._calculate_depth(asks, depth_levels=10)
            total_liquidity = bid_liquidity + ask_liquidity
            
            # Calculate spread
            best_bid = float(bids[0][0]) if bids else 0
            best_ask = float(asks[0][0]) if asks else 0
            mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
            spread_bps = ((best_ask - best_bid) / mid_price * 10000) if mid_price > 0 else 0
            
            # Liquidity score (0-100)
            liquidity_score = min(total_liquidity / 100000 * 100, 100)
            
            # Check if sufficient for trading
            sufficient = (
                total_liquidity > 50000 and  # Min $50k liquidity
                spread_bps < 10  # Max 10 bps spread
            )
            
            analysis = {
                'sufficient_liquidity': sufficient,
                'bid_liquidity': bid_liquidity,
                'ask_liquidity': ask_liquidity,
                'total_liquidity': total_liquidity,
                'spread_bps': spread_bps,
                'liquidity_score': liquidity_score,
                'mid_price': mid_price
            }
            
            self.liquidity_history[symbol] = analysis
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing liquidity: {e}")
            return {
                'sufficient_liquidity': False,
                'error': str(e)
            }
    
    def _calculate_depth(self, orders: List, depth_levels: int = 10) -> float:
        """Calculate total liquidity depth"""
        try:
            total = 0
            for i, (price, volume) in enumerate(orders[:depth_levels]):
                total += float(price) * float(volume)
            return total
        except Exception as e:
            return 0
    
    def get_liquidity_score(self, symbol: str) -> float:
        """Get liquidity score (0-100)"""
        if symbol in self.liquidity_history:
            return self.liquidity_history[symbol].get('liquidity_score', 0)
        return 0

def get_liquidity_analyzer():
    """Factory function"""
    return LiquidityAnalyzer()
