"""Market intelligence and regime detection."""
import logging
from typing import List, Dict
from enum import Enum

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"

class MarketIntelligence:
    """Market intelligence analyzer."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_regime = MarketRegime.SIDEWAYS
    
    def detect_regime(self, prices: List[float]) -> MarketRegime:
        """Detect market regime."""
        if len(prices) < 10:
            return MarketRegime.SIDEWAYS
        
        # Calculate trend
        returns = [(prices[i] - prices[i-1])/prices[i-1] for i in range(1, len(prices))]
        avg_return = sum(returns) / len(returns)
        volatility = (sum((r - avg_return)**2 for r in returns) / len(returns)) ** 0.5
        
        if volatility > 0.05:
            return MarketRegime.VOLATILE
        elif avg_return > 0.01:
            return MarketRegime.BULL
        elif avg_return < -0.01:
            return MarketRegime.BEAR
        else:
            return MarketRegime.SIDEWAYS
    
    def analyze_liquidity(self, orderbook: Dict) -> Dict:
        """Analyze market liquidity."""
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        bid_depth = sum(b[1] for b in bids[:10]) if bids else 0
        ask_depth = sum(a[1] for a in asks[:10]) if asks else 0
        
        return {
            'bid_depth': bid_depth,
            'ask_depth': ask_depth,
            'total_depth': bid_depth + ask_depth,
            'imbalance': (bid_depth - ask_depth) / (bid_depth + ask_depth) if bid_depth + ask_depth > 0 else 0
        }
    
    def volume_profile(self, trades: List[Dict]) -> Dict:
        """Analyze volume profile."""
        if not trades:
            return {}
        
        total_volume = sum(t.get('volume', 0) for t in trades)
        buy_volume = sum(t.get('volume', 0) for t in trades if t.get('side') == 'buy')
        
        return {
            'total_volume': total_volume,
            'buy_volume': buy_volume,
            'sell_volume': total_volume - buy_volume,
            'buy_pressure': buy_volume / total_volume if total_volume > 0 else 0.5
        }
