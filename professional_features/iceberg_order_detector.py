"""
Iceberg Order Detector - Detects hidden large orders
Identifies iceberg orders in the orderbook
"""
import logging
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

class IcebergOrderDetector:
    """Detects iceberg (hidden) orders"""
    
    def __init__(self, detection_threshold: float = 0.1):
        self.detection_threshold = detection_threshold
        self.detected_icebergs = {}
        self.orderbook_history = {}
        logger.info("✅ IcebergOrderDetector initialized")
    
    def detect(self, symbol: str, orderbook: Dict) -> List[Dict]:
        """Detect iceberg orders in orderbook"""
        try:
            # Initialize history for symbol
            if symbol not in self.orderbook_history:
                self.orderbook_history[symbol] = []
            
            # Store current orderbook
            self.orderbook_history[symbol].append({
                'orderbook': orderbook,
                'timestamp': time.time()
            })
            
            # Keep only recent history
            if len(self.orderbook_history[symbol]) > 100:
                self.orderbook_history[symbol] = self.orderbook_history[symbol][-50:]
            
            detected = []
            
            # Look for signs of iceberg orders:
            # 1. Same price level repeatedly refilled
            # 2. Large order that doesn't move price much
            # 3. Consistent volume at specific price level
            
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            # Check bid side
            for i, (price, volume) in enumerate(bids[:10]):
                if self._is_iceberg_candidate(symbol, 'bid', float(price), float(volume)):
                    detected.append({
                        'side': 'bid',
                        'price': float(price),
                        'visible_volume': float(volume),
                        'confidence': 0.7,
                        'timestamp': time.time()
                    })
            
            # Check ask side
            for i, (price, volume) in enumerate(asks[:10]):
                if self._is_iceberg_candidate(symbol, 'ask', float(price), float(volume)):
                    detected.append({
                        'side': 'ask',
                        'price': float(price),
                        'visible_volume': float(volume),
                        'confidence': 0.7,
                        'timestamp': time.time()
                    })
            
            if detected:
                logger.debug(f"Detected {len(detected)} potential iceberg orders for {symbol}")
            
            return detected
            
        except Exception as e:
            logger.error(f"Error detecting icebergs: {e}")
            return []
    
    def _is_iceberg_candidate(self, symbol: str, side: str, price: float, volume: float) -> bool:
        """Check if order might be iceberg"""
        try:
            # Simple heuristic: large order that appears consistently
            # In full implementation, would analyze refill patterns
            return volume > 10000  # Placeholder threshold
            
        except Exception as e:
            return False

def get_iceberg_order_detector():
    """Factory function"""
    return IcebergOrderDetector()
