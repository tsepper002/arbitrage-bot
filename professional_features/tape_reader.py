"""
Tape Reader - Level 2 Market Data Analysis
Reads order flow and execution patterns from the tape
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class TapeReader:
    """Reads and analyzes Level 2 market data and execution tape"""
    
    def __init__(self, max_history: int = 1000):
        self.tape_history = deque(maxlen=max_history)
        self.execution_patterns = []
        
    async def read_tape(self, symbol: str, orderbook: Dict, trades: List[Dict]) -> Dict:
        """
        Read and analyze the tape (recent trades)
        
        Args:
            symbol: Trading symbol
            orderbook: Current order book
            trades: Recent trades
            
        Returns:
            Tape analysis results
        """
        try:
            if not trades:
                return self._create_empty_tape_result(symbol)
            
            # Analyze recent trade flow
            buy_volume = sum(t['size'] for t in trades if t.get('side') == 'buy')
            sell_volume = sum(t['size'] for t in trades if t.get('side') == 'sell')
            
            total_volume = buy_volume + sell_volume
            if total_volume == 0:
                return self._create_empty_tape_result(symbol)
            
            # Calculate buy/sell pressure
            buy_pressure = (buy_volume / total_volume) * 100
            sell_pressure = (sell_volume / total_volume) * 100
            
            # Analyze execution patterns
            aggressive_buys = sum(1 for t in trades if t.get('side') == 'buy' and t.get('aggressive', True))
            aggressive_sells = sum(1 for t in trades if t.get('side') == 'sell' and t.get('aggressive', True))
            
            # Detect large prints
            avg_size = total_volume / len(trades)
            large_prints = [t for t in trades if t['size'] > avg_size * 3]
            
            # Calculate momentum from tape
            tape_momentum = self._calculate_tape_momentum(trades)
            
            # Generate signal
            signal = self._generate_tape_signal(buy_pressure, tape_momentum, len(large_prints))
            
            result = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'buy_pressure': buy_pressure,
                'sell_pressure': sell_pressure,
                'aggressive_buys': aggressive_buys,
                'aggressive_sells': aggressive_sells,
                'large_prints': len(large_prints),
                'tape_momentum': tape_momentum,
                'signal': signal
            }
            
            self.tape_history.append(result)
            return result
            
        except Exception as e:
            logger.error(f"Error reading tape: {e}")
            return self._create_empty_tape_result(symbol)
    
    def _calculate_tape_momentum(self, trades: List[Dict]) -> float:
        """
        Calculate momentum from tape
        
        Args:
            trades: Recent trades
            
        Returns:
            Momentum score (-1 to 1)
        """
        if len(trades) < 2:
            return 0.0
        
        # Calculate price momentum
        prices = [t['price'] for t in trades]
        price_change = (prices[-1] - prices[0]) / prices[0] if prices[0] != 0 else 0
        
        # Normalize to -1 to 1 range
        return max(min(price_change * 100, 1.0), -1.0)
    
    def _generate_tape_signal(self, buy_pressure: float, momentum: float, large_prints: int) -> str:
        """Generate trading signal from tape analysis"""
        # Strong buy signal
        if buy_pressure > 65 and momentum > 0.3:
            return 'STRONG_BUY'
        elif buy_pressure > 55 and momentum > 0.1:
            return 'BUY'
        
        # Strong sell signal
        elif buy_pressure < 35 and momentum < -0.3:
            return 'STRONG_SELL'
        elif buy_pressure < 45 and momentum < -0.1:
            return 'SELL'
        
        else:
            return 'NEUTRAL'
    
    def _create_empty_tape_result(self, symbol: str) -> Dict:
        """Create empty tape analysis result"""
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'buy_pressure': 50,
            'sell_pressure': 50,
            'signal': 'NEUTRAL'
        }
    
    async def analyze_orderbook_depth(self, orderbook: Dict) -> Dict:
        """
        Analyze order book depth and imbalances
        
        Args:
            orderbook: Current order book data
            
        Returns:
            Depth analysis results
        """
        try:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])
            
            if not bids or not asks:
                return {}
            
            # Calculate volume at different depth levels
            levels = [5, 10, 20]
            depth_analysis = {}
            
            for level in levels:
                bid_volume = sum(b[1] for b in bids[:level])
                ask_volume = sum(a[1] for a in asks[:level])
                
                total = bid_volume + ask_volume
                if total > 0:
                    imbalance = (bid_volume - ask_volume) / total
                else:
                    imbalance = 0
                
                depth_analysis[f'level_{level}'] = {
                    'bid_volume': bid_volume,
                    'ask_volume': ask_volume,
                    'imbalance': imbalance
                }
            
            # Calculate weighted average imbalance
            avg_imbalance = sum(d['imbalance'] for d in depth_analysis.values()) / len(depth_analysis)
            
            return {
                'timestamp': datetime.now().isoformat(),
                'depth_levels': depth_analysis,
                'average_imbalance': avg_imbalance,
                'signal': 'BUY' if avg_imbalance > 0.2 else 'SELL' if avg_imbalance < -0.2 else 'NEUTRAL'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing orderbook depth: {e}")
            return {}
    
    async def detect_execution_patterns(self, trades: List[Dict]) -> Dict:
        """
        Detect patterns in trade execution
        
        Args:
            trades: Recent trades
            
        Returns:
            Detected patterns
        """
        try:
            patterns = {
                'sweep': self._detect_sweep_pattern(trades),
                'absorption': self._detect_absorption_pattern(trades),
                'iceberg': self._detect_iceberg_pattern(trades)
            }
            
            return {
                'timestamp': datetime.now().isoformat(),
                'patterns': patterns,
                'pattern_count': sum(1 for p in patterns.values() if p)
            }
            
        except Exception as e:
            logger.error(f"Error detecting execution patterns: {e}")
            return {}
    
    def _detect_sweep_pattern(self, trades: List[Dict]) -> bool:
        """Detect if trades are sweeping through order book"""
        if len(trades) < 3:
            return False
        
        # Check if multiple trades in same direction with increasing prices (buy) or decreasing (sell)
        buy_trades = [t for t in trades if t.get('side') == 'buy']
        if len(buy_trades) >= 3:
            prices = [t['price'] for t in buy_trades[-3:]]
            return all(prices[i] <= prices[i+1] for i in range(len(prices)-1))
        
        return False
    
    def _detect_absorption_pattern(self, trades: List[Dict]) -> bool:
        """Detect if large volume is being absorbed"""
        if len(trades) < 5:
            return False
        
        # Check if multiple trades at similar price with increasing size
        recent = trades[-5:]
        avg_price = sum(t['price'] for t in recent) / len(recent)
        price_variance = sum(abs(t['price'] - avg_price) for t in recent) / len(recent)
        
        # Low price variance but high volume = absorption
        return price_variance < (avg_price * 0.001)
    
    def _detect_iceberg_pattern(self, trades: List[Dict]) -> bool:
        """Detect iceberg order pattern"""
        if len(trades) < 10:
            return False
        
        # Check for repeated similar-sized trades at same price level
        recent = trades[-10:]
        sizes = [t['size'] for t in recent]
        avg_size = sum(sizes) / len(sizes)
        
        # Count how many trades are close to average size
        similar_size_count = sum(1 for s in sizes if abs(s - avg_size) < avg_size * 0.2)
        
        return similar_size_count >= 7  # 70% similarity suggests iceberg
    
    def get_tape_stats(self) -> Dict:
        """Get tape reader statistics"""
        return {
            'tape_history': len(self.tape_history),
            'patterns_detected': len(self.execution_patterns),
            'last_update': datetime.now().isoformat()
        }
