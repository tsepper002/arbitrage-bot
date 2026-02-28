"""
Market Manipulation Detector - Detects market manipulation
Identifies pump & dump, spoofing, wash trading
"""
import logging
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

class MarketManipulationDetector:
    """Detects various forms of market manipulation"""
    
    def __init__(self):
        self.detected_events = []
        self.trade_history = {}
        logger.info("✅ MarketManipulationDetector initialized")
    
    def detect(self, symbol: str, orderbook: Dict, recent_trades: List[Dict]) -> List[Dict]:
        """Detect manipulation patterns"""
        try:
            detected = []
            
            # Detect spoofing (large orders that get cancelled)
            spoofing = self._detect_spoofing(symbol, orderbook)
            if spoofing:
                detected.append(spoofing)
            
            # Detect pump and dump patterns
            pump_dump = self._detect_pump_dump(symbol, recent_trades)
            if pump_dump:
                detected.append(pump_dump)
            
            # Detect wash trading
            wash_trading = self._detect_wash_trading(symbol, recent_trades)
            if wash_trading:
                detected.append(wash_trading)
            
            if detected:
                logger.warning(f"⚠️ Detected {len(detected)} manipulation patterns for {symbol}")
                self.detected_events.extend(detected)
            
            return detected
            
        except Exception as e:
            logger.error(f"Error detecting manipulation: {e}")
            return []
    
    def _detect_spoofing(self, symbol: str, orderbook: Dict) -> Optional[Dict]:
        """Detect spoofing patterns"""
        try:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            if not bids or not asks:
                return None
            
            # Look for unusually large orders far from mid price
            if len(bids) > 5:
                large_bid = max([float(b[1]) for b in bids[:5]])
                if large_bid > 100000:  # Placeholder threshold
                    return {
                        'type': 'spoofing',
                        'side': 'bid',
                        'symbol': symbol,
                        'confidence': 0.6,
                        'timestamp': time.time()
                    }
            
            return None
            
        except Exception as e:
            return None
    
    def _detect_pump_dump(self, symbol: str, trades: List[Dict]) -> Optional[Dict]:
        """Detect pump & dump patterns"""
        try:
            if len(trades) < 10:
                return None
            
            # Look for rapid price increase followed by rapid decrease
            prices = [float(t.get('price', 0)) for t in trades[-20:]]
            if len(prices) < 20:
                return None
            
            # Simple heuristic: price spike > 5% in short time
            max_price = max(prices)
            min_price = min(prices)
            price_change = (max_price - min_price) / min_price if min_price > 0 else 0
            
            if price_change > 0.05:  # 5% threshold
                return {
                    'type': 'pump_dump',
                    'symbol': symbol,
                    'price_change_pct': price_change * 100,
                    'confidence': 0.7,
                    'timestamp': time.time()
                }
            
            return None
            
        except Exception as e:
            return None
    
    def _detect_wash_trading(self, symbol: str, trades: List[Dict]) -> Optional[Dict]:
        """Detect wash trading patterns"""
        try:
            # Look for trades with same size at same price from same entity
            # Simplified: detect unusual trade patterns
            if len(trades) < 5:
                return None
            
            # Check for repetitive trade sizes
            trade_sizes = [float(t.get('amount', 0)) for t in trades[-10:]]
            if len(set(trade_sizes)) < len(trade_sizes) / 2:  # More than 50% duplicate sizes
                return {
                    'type': 'wash_trading',
                    'symbol': symbol,
                    'confidence': 0.5,
                    'timestamp': time.time()
                }
            
            return None
            
        except Exception as e:
            return None

def get_market_manipulation_detector():
    """Factory function"""
    return MarketManipulationDetector()
