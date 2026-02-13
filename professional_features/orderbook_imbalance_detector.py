"""
Order Book Imbalance Detector
Analyzes order book imbalance to predict short-term price movements
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class OrderBookSnapshot:
    """Order book snapshot data"""
    timestamp: datetime
    bids: List[Tuple[float, float]]  # [(price, size), ...]
    asks: List[Tuple[float, float]]
    exchange: str
    symbol: str


@dataclass
class ImbalanceSignal:
    """Imbalance analysis result"""
    timestamp: datetime
    imbalance_ratio: float  # -1 to 1, negative = sell pressure, positive = buy pressure
    buy_pressure: float
    sell_pressure: float
    spread: float
    mid_price: float
    signal: str  # 'STRONG_BUY', 'BUY', 'NEUTRAL', 'SELL', 'STRONG_SELL'
    confidence: float
    depth_imbalance: float
    volume_imbalance: float


class OrderBookImbalanceDetector:
    """
    Detects and analyzes order book imbalance
    
    Used by top HFT firms like Jane Street for micro-predictions
    """
    
    def __init__(self, depth_levels: int = 10, history_size: int = 100):
        self.depth_levels = depth_levels
        self.history_size = history_size
        self.imbalance_history = deque(maxlen=history_size)
        
    def analyze_orderbook(self, orderbook: OrderBookSnapshot) -> ImbalanceSignal:
        """
        Analyze order book imbalance
        
        Args:
            orderbook: Current order book snapshot
            
        Returns:
            ImbalanceSignal with analysis results
        """
        try:
            # Extract bid and ask data
            bids = orderbook.bids[:self.depth_levels]
            asks = orderbook.asks[:self.depth_levels]
            
            if not bids or not asks:
                return self._neutral_signal(orderbook.timestamp)
            
            # Calculate mid price and spread
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            
            # Calculate buy and sell pressure
            buy_pressure = self._calculate_buy_pressure(bids)
            sell_pressure = self._calculate_sell_pressure(asks)
            
            # Calculate imbalance ratio
            total_pressure = buy_pressure + sell_pressure
            if total_pressure > 0:
                imbalance_ratio = (buy_pressure - sell_pressure) / total_pressure
            else:
                imbalance_ratio = 0.0
            
            # Calculate depth imbalance (weighted by price proximity)
            depth_imbalance = self._calculate_depth_imbalance(bids, asks, mid_price)
            
            # Calculate volume imbalance
            volume_imbalance = self._calculate_volume_imbalance(bids, asks)
            
            # Generate signal
            signal, confidence = self._generate_signal(
                imbalance_ratio, 
                depth_imbalance, 
                volume_imbalance,
                spread,
                mid_price
            )
            
            # Create result
            result = ImbalanceSignal(
                timestamp=orderbook.timestamp,
                imbalance_ratio=imbalance_ratio,
                buy_pressure=buy_pressure,
                sell_pressure=sell_pressure,
                spread=spread,
                mid_price=mid_price,
                signal=signal,
                confidence=confidence,
                depth_imbalance=depth_imbalance,
                volume_imbalance=volume_imbalance
            )
            
            # Store in history
            self.imbalance_history.append(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing orderbook: {e}")
            return self._neutral_signal(orderbook.timestamp)
    
    def _calculate_buy_pressure(self, bids: List[Tuple[float, float]]) -> float:
        """Calculate total buy pressure from bids"""
        return sum(price * size for price, size in bids)
    
    def _calculate_sell_pressure(self, asks: List[Tuple[float, float]]) -> float:
        """Calculate total sell pressure from asks"""
        return sum(price * size for price, size in asks)
    
    def _calculate_depth_imbalance(
        self, 
        bids: List[Tuple[float, float]], 
        asks: List[Tuple[float, float]],
        mid_price: float
    ) -> float:
        """
        Calculate depth imbalance weighted by price proximity to mid
        Closer orders have more weight
        """
        bid_weighted = sum(
            size * (1 / (1 + abs(price - mid_price) / mid_price))
            for price, size in bids
        )
        ask_weighted = sum(
            size * (1 / (1 + abs(price - mid_price) / mid_price))
            for price, size in asks
        )
        
        total = bid_weighted + ask_weighted
        if total > 0:
            return (bid_weighted - ask_weighted) / total
        return 0.0
    
    def _calculate_volume_imbalance(
        self,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]]
    ) -> float:
        """Calculate simple volume imbalance"""
        bid_volume = sum(size for _, size in bids)
        ask_volume = sum(size for _, size in asks)
        
        total_volume = bid_volume + ask_volume
        if total_volume > 0:
            return (bid_volume - ask_volume) / total_volume
        return 0.0
    
    def _generate_signal(
        self,
        imbalance_ratio: float,
        depth_imbalance: float,
        volume_imbalance: float,
        spread: float,
        mid_price: float
    ) -> Tuple[str, float]:
        """
        Generate trading signal from imbalance metrics
        
        Returns:
            (signal, confidence) tuple
        """
        # Combine metrics with weights
        combined_score = (
            0.4 * imbalance_ratio +
            0.3 * depth_imbalance +
            0.3 * volume_imbalance
        )
        
        # Calculate confidence based on consistency
        consistency = 1.0 - abs(imbalance_ratio - depth_imbalance)
        spread_factor = 1.0 / (1 + spread / mid_price * 100)  # Lower spread = higher confidence
        confidence = min(consistency * spread_factor, 1.0)
        
        # Generate signal based on thresholds
        if combined_score > 0.4:
            signal = 'STRONG_BUY'
        elif combined_score > 0.15:
            signal = 'BUY'
        elif combined_score < -0.4:
            signal = 'STRONG_SELL'
        elif combined_score < -0.15:
            signal = 'SELL'
        else:
            signal = 'NEUTRAL'
        
        return signal, confidence
    
    def _neutral_signal(self, timestamp: datetime) -> ImbalanceSignal:
        """Return neutral signal"""
        return ImbalanceSignal(
            timestamp=timestamp,
            imbalance_ratio=0.0,
            buy_pressure=0.0,
            sell_pressure=0.0,
            spread=0.0,
            mid_price=0.0,
            signal='NEUTRAL',
            confidence=0.0,
            depth_imbalance=0.0,
            volume_imbalance=0.0
        )
    
    def get_imbalance_trend(self, periods: int = 10) -> float:
        """
        Calculate trend of imbalance over recent periods
        
        Args:
            periods: Number of recent periods to analyze
            
        Returns:
            Trend value (positive = increasing buy pressure)
        """
        if len(self.imbalance_history) < 2:
            return 0.0
        
        recent = list(self.imbalance_history)[-periods:]
        if len(recent) < 2:
            return 0.0
        
        # Calculate linear regression trend
        x = np.arange(len(recent))
        y = np.array([s.imbalance_ratio for s in recent])
        
        # Simple linear regression
        if len(x) > 1:
            slope = np.polyfit(x, y, 1)[0]
            return slope
        
        return 0.0
    
    def get_statistics(self) -> Dict:
        """Get imbalance statistics"""
        if not self.imbalance_history:
            return {}
        
        signals = list(self.imbalance_history)
        
        return {
            'avg_imbalance': np.mean([s.imbalance_ratio for s in signals]),
            'std_imbalance': np.std([s.imbalance_ratio for s in signals]),
            'avg_confidence': np.mean([s.confidence for s in signals]),
            'buy_signals': sum(1 for s in signals if 'BUY' in s.signal),
            'sell_signals': sum(1 for s in signals if 'SELL' in s.signal),
            'neutral_signals': sum(1 for s in signals if s.signal == 'NEUTRAL'),
            'strong_signals': sum(1 for s in signals if 'STRONG' in s.signal),
            'current_trend': self.get_imbalance_trend()
        }
