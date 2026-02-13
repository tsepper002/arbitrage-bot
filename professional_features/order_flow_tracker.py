"""
Order Flow Tracker
Tracks large orders and institutional activity
"""
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class OrderFlowTracker:
    """Tracks order flow to detect whales and institutional activity"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.whale_threshold = self.config.get('whale_threshold', 100000)  # USD
        self.institutional_threshold = self.config.get('institutional_threshold', 500000)
        self.lookback_period = self.config.get('lookback_period', 3600)  # seconds
        
        # Order flow data
        self.order_flow = defaultdict(lambda: deque(maxlen=1000))
        self.whale_orders = []
        self.institutional_flow = defaultdict(float)
        
        # Statistics
        self.stats = {
            'total_orders': 0,
            'whale_orders': 0,
            'institutional_orders': 0,
            'total_volume': 0
        }
        
        logger.info("OrderFlowTracker initialized")
    
    async def track_order(self, exchange: str, symbol: str, order: Dict) -> Optional[Dict]:
        """
        Track a single order
        
        Args:
            exchange: Exchange name
            symbol: Trading pair
            order: Order data
            
        Returns:
            Signal if whale/institutional activity detected
        """
        try:
            size = order.get('amount', 0) * order.get('price', 0)
            side = order.get('side', 'unknown')
            timestamp = order.get('timestamp', datetime.now())
            
            # Store order
            flow_key = f"{exchange}:{symbol}"
            self.order_flow[flow_key].append({
                'timestamp': timestamp,
                'side': side,
                'size': size,
                'price': order.get('price'),
                'amount': order.get('amount')
            })
            
            self.stats['total_orders'] += 1
            self.stats['total_volume'] += size
            
            # Check for whale order
            if size >= self.whale_threshold:
                self.stats['whale_orders'] += 1
                signal = self._create_whale_signal(exchange, symbol, order, size)
                self.whale_orders.append(signal)
                return signal
            
            # Check for institutional activity
            if size >= self.institutional_threshold:
                self.stats['institutional_orders'] += 1
                self.institutional_flow[flow_key] += size if side == 'buy' else -size
                return self._create_institutional_signal(exchange, symbol, order, size)
            
            return None
            
        except Exception as e:
            logger.error(f"Error tracking order: {e}")
            return None
    
    def _create_whale_signal(self, exchange: str, symbol: str, 
                            order: Dict, size: float) -> Dict:
        """Create signal for whale order"""
        return {
            'type': 'whale_order',
            'exchange': exchange,
            'symbol': symbol,
            'side': order.get('side'),
            'size': size,
            'price': order.get('price'),
            'timestamp': order.get('timestamp', datetime.now()),
            'impact': 'high' if size > self.whale_threshold * 2 else 'medium'
        }
    
    def _create_institutional_signal(self, exchange: str, symbol: str,
                                    order: Dict, size: float) -> Dict:
        """Create signal for institutional order"""
        return {
            'type': 'institutional_order',
            'exchange': exchange,
            'symbol': symbol,
            'side': order.get('side'),
            'size': size,
            'price': order.get('price'),
            'timestamp': order.get('timestamp', datetime.now()),
            'impact': 'very_high'
        }
    
    def analyze_flow(self, exchange: str, symbol: str, 
                     timeframe: int = 300) -> Dict:
        """
        Analyze order flow for a symbol
        
        Args:
            exchange: Exchange name
            symbol: Trading pair
            timeframe: Analysis timeframe in seconds
            
        Returns:
            Flow analysis
        """
        flow_key = f"{exchange}:{symbol}"
        orders = self.order_flow.get(flow_key, deque())
        
        if not orders:
            return {'status': 'no_data'}
        
        cutoff_time = datetime.now() - timedelta(seconds=timeframe)
        recent_orders = [o for o in orders if o['timestamp'] > cutoff_time]
        
        if not recent_orders:
            return {'status': 'no_recent_data'}
        
        # Calculate flow metrics
        buy_volume = sum(o['size'] for o in recent_orders if o['side'] == 'buy')
        sell_volume = sum(o['size'] for o in recent_orders if o['side'] == 'sell')
        total_volume = buy_volume + sell_volume
        
        buy_count = sum(1 for o in recent_orders if o['side'] == 'buy')
        sell_count = sum(1 for o in recent_orders if o['side'] == 'sell')
        
        # Determine flow direction
        if total_volume == 0:
            direction = 'neutral'
            strength = 0
        else:
            net_flow = buy_volume - sell_volume
            direction = 'bullish' if net_flow > 0 else 'bearish' if net_flow < 0 else 'neutral'
            strength = abs(net_flow) / total_volume
        
        return {
            'status': 'ok',
            'exchange': exchange,
            'symbol': symbol,
            'timeframe': timeframe,
            'direction': direction,
            'strength': strength,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'total_volume': total_volume,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'net_flow': buy_volume - sell_volume,
            'imbalance': (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0
        }
    
    def get_whale_activity(self, symbol: Optional[str] = None,
                          minutes: int = 60) -> List[Dict]:
        """Get recent whale activity"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        recent_whales = [
            w for w in self.whale_orders
            if w['timestamp'] > cutoff_time and (not symbol or w['symbol'] == symbol)
        ]
        
        return recent_whales
    
    def get_institutional_flow(self, exchange: str, symbol: str) -> float:
        """Get net institutional flow for a symbol"""
        flow_key = f"{exchange}:{symbol}"
        return self.institutional_flow.get(flow_key, 0.0)
    
    def detect_accumulation_distribution(self, exchange: str, symbol: str,
                                        period: int = 3600) -> Dict:
        """
        Detect accumulation or distribution patterns
        
        Args:
            exchange: Exchange name
            symbol: Trading pair
            period: Analysis period in seconds
            
        Returns:
            Pattern analysis
        """
        flow = self.analyze_flow(exchange, symbol, period)
        
        if flow.get('status') != 'ok':
            return {'pattern': 'unknown', 'confidence': 0}
        
        imbalance = flow.get('imbalance', 0)
        strength = flow.get('strength', 0)
        
        # Determine pattern
        if imbalance > 0.3 and strength > 0.5:
            pattern = 'strong_accumulation'
            confidence = min(0.9, strength)
        elif imbalance > 0.1:
            pattern = 'accumulation'
            confidence = min(0.7, strength)
        elif imbalance < -0.3 and strength > 0.5:
            pattern = 'strong_distribution'
            confidence = min(0.9, strength)
        elif imbalance < -0.1:
            pattern = 'distribution'
            confidence = min(0.7, strength)
        else:
            pattern = 'neutral'
            confidence = 0.5
        
        return {
            'pattern': pattern,
            'confidence': confidence,
            'imbalance': imbalance,
            'strength': strength,
            'volume': flow.get('total_volume', 0)
        }
    
    def get_smart_money_signal(self, exchange: str, symbol: str) -> Optional[str]:
        """
        Generate smart money following signal
        
        Returns:
            'buy', 'sell', or None
        """
        # Analyze recent institutional flow
        inst_flow = self.get_institutional_flow(exchange, symbol)
        
        # Analyze whale activity
        recent_whales = self.get_whale_activity(symbol, minutes=30)
        whale_sentiment = sum(
            1 if w['side'] == 'buy' else -1
            for w in recent_whales
        )
        
        # Analyze accumulation/distribution
        pattern = self.detect_accumulation_distribution(exchange, symbol, 1800)
        
        # Combine signals
        if pattern['pattern'] in ['strong_accumulation', 'accumulation'] and \
           inst_flow > 0 and whale_sentiment > 0:
            return 'buy'
        elif pattern['pattern'] in ['strong_distribution', 'distribution'] and \
             inst_flow < 0 and whale_sentiment < 0:
            return 'sell'
        
        return None
    
    def get_statistics(self) -> Dict:
        """Get tracking statistics"""
        return {
            **self.stats,
            'whale_percentage': (self.stats['whale_orders'] / max(1, self.stats['total_orders'])) * 100,
            'institutional_percentage': (self.stats['institutional_orders'] / max(1, self.stats['total_orders'])) * 100
        }
    
    def reset(self):
        """Reset tracker data"""
        self.order_flow.clear()
        self.whale_orders.clear()
        self.institutional_flow.clear()
        self.stats = {
            'total_orders': 0,
            'whale_orders': 0,
            'institutional_orders': 0,
            'total_volume': 0
        }
        logger.info("OrderFlowTracker reset")


# Example usage
if __name__ == "__main__":
    async def main():
        tracker = OrderFlowTracker({'whale_threshold': 50000})
        
        # Simulate some orders
        test_orders = [
            {'amount': 10, 'price': 50000, 'side': 'buy', 'timestamp': datetime.now()},
            {'amount': 5, 'price': 50100, 'side': 'sell', 'timestamp': datetime.now()},
            {'amount': 100, 'price': 50000, 'side': 'buy', 'timestamp': datetime.now()},  # Whale
        ]
        
        for order in test_orders:
            signal = await tracker.track_order('binance', 'BTC/USDT', order)
            if signal:
                print(f"Signal detected: {signal}")
        
        # Analyze flow
        flow = tracker.analyze_flow('binance', 'BTC/USDT', 300)
        print(f"Flow analysis: {flow}")
        
        # Get statistics
        stats = tracker.get_statistics()
        print(f"Statistics: {stats}")
    
    asyncio.run(main())
