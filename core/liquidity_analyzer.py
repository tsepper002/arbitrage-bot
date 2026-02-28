"""Liquidity analyzer."""
import logging

logger = logging.getLogger(__name__)

class LiquidityAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_orderbook(self, orderbook):
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        bid_depth = sum(b[1] for b in bids[:10])
        ask_depth = sum(a[1] for a in asks[:10])
        spread = asks[0][0] - bids[0][0] if len(bids) > 0 and len(asks) > 0 else 0
        
        return {
            'bid_depth': bid_depth,
            'ask_depth': ask_depth,
            'spread': spread,
            'liquidity_score': (bid_depth + ask_depth) / spread if spread > 0 else 0
        }
