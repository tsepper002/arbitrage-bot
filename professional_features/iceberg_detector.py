"""
Iceberg Orders Detector
Detects hidden large orders through tape reading and volume analysis
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a single trade"""
    timestamp: datetime
    price: float
    size: float
    side: str  # 'buy' or 'sell'
    

@dataclass
class IcebergSignal:
    """Detected iceberg order signal"""
    timestamp: datetime
    symbol: str
    side: str
    estimated_size: float
    confidence: float
    avg_chunk_size: float
    num_chunks: int
    price_range: Tuple[float, float]


class IcebergDetector:
    """Detects iceberg orders through pattern analysis"""
    
    def __init__(self, 
                 min_chunks: int = 3,
                 chunk_similarity_threshold: float = 0.3,
                 time_window_seconds: int = 300):
        self.min_chunks = min_chunks
        self.chunk_similarity_threshold = chunk_similarity_threshold
        self.time_window_seconds = time_window_seconds
        
        self.trade_history: Dict[str, List[Trade]] = defaultdict(list)
        self.detected_icebergs: List[IcebergSignal] = []
        
        logger.info(f"IcebergDetector initialized: min_chunks={min_chunks}, "
                   f"similarity_threshold={chunk_similarity_threshold}")
    
    def add_trade(self, symbol: str, price: float, size: float, side: str):
        """Add a trade to history"""
        trade = Trade(
            timestamp=datetime.now(),
            price=price,
            size=size,
            side=side
        )
        
        self.trade_history[symbol].append(trade)
        
        # Clean old trades
        cutoff = datetime.now() - timedelta(seconds=self.time_window_seconds * 2)
        self.trade_history[symbol] = [
            t for t in self.trade_history[symbol] if t.timestamp > cutoff
        ]
    
    def detect_icebergs(self, symbol: str) -> List[IcebergSignal]:
        """Detect iceberg orders for a symbol"""
        if symbol not in self.trade_history:
            return []
        
        trades = self.trade_history[symbol]
        if len(trades) < self.min_chunks:
            return []
        
        # Analyze recent trades within time window
        cutoff = datetime.now() - timedelta(seconds=self.time_window_seconds)
        recent_trades = [t for t in trades if t.timestamp > cutoff]
        
        if len(recent_trades) < self.min_chunks:
            return []
        
        signals = []
        
        # Detect buy-side icebergs
        buy_signal = self._detect_iceberg_side(recent_trades, 'buy', symbol)
        if buy_signal:
            signals.append(buy_signal)
        
        # Detect sell-side icebergs
        sell_signal = self._detect_iceberg_side(recent_trades, 'sell', symbol)
        if sell_signal:
            signals.append(sell_signal)
        
        # Store detected icebergs
        self.detected_icebergs.extend(signals)
        
        return signals
    
    def _detect_iceberg_side(self, trades: List[Trade], side: str, symbol: str) -> Optional[IcebergSignal]:
        """Detect iceberg on one side (buy or sell)"""
        side_trades = [t for t in trades if t.side == side]
        
        if len(side_trades) < self.min_chunks:
            return None
        
        # Analyze trade sizes for clustering
        sizes = [t.size for t in side_trades]
        
        # Find repeated similar-sized trades
        chunks = self._find_similar_chunks(sizes)
        
        if len(chunks) < self.min_chunks:
            return None
        
        # Calculate statistics
        avg_chunk_size = np.mean([sizes[i] for i in chunks])
        total_size = sum([sizes[i] for i in chunks])
        
        prices = [side_trades[i].price for i in chunks]
        price_range = (min(prices), max(prices))
        
        # Calculate confidence based on chunk similarity and frequency
        size_variance = np.std([sizes[i] for i in chunks]) / avg_chunk_size if avg_chunk_size > 0 else 1
        confidence = min(1.0, (1.0 - size_variance) * (len(chunks) / self.min_chunks))
        
        if confidence < 0.5:
            return None
        
        logger.info(f"Detected iceberg for {symbol} {side}: "
                   f"{len(chunks)} chunks, avg size {avg_chunk_size:.2f}, confidence {confidence:.2%}")
        
        return IcebergSignal(
            timestamp=datetime.now(),
            symbol=symbol,
            side=side,
            estimated_size=total_size,
            confidence=confidence,
            avg_chunk_size=avg_chunk_size,
            num_chunks=len(chunks),
            price_range=price_range
        )
    
    def _find_similar_chunks(self, sizes: List[float]) -> List[int]:
        """Find indices of similar-sized trades (potential iceberg chunks)"""
        if not sizes:
            return []
        
        chunks = []
        median_size = np.median(sizes)
        
        for i, size in enumerate(sizes):
            # Check if size is similar to median (within threshold)
            if abs(size - median_size) / median_size < self.chunk_similarity_threshold:
                chunks.append(i)
        
        return chunks
    
    def get_statistics(self) -> Dict:
        """Get detection statistics"""
        if not self.detected_icebergs:
            return {
                'total_detected': 0,
                'by_side': {},
                'avg_confidence': 0.0,
                'avg_chunks': 0.0
            }
        
        by_side = defaultdict(int)
        confidences = []
        num_chunks = []
        
        for signal in self.detected_icebergs:
            by_side[signal.side] += 1
            confidences.append(signal.confidence)
            num_chunks.append(signal.num_chunks)
        
        return {
            'total_detected': len(self.detected_icebergs),
            'by_side': dict(by_side),
            'avg_confidence': np.mean(confidences),
            'avg_chunks': np.mean(num_chunks),
            'total_estimated_volume': sum(s.estimated_size for s in self.detected_icebergs)
        }
    
    def analyze_order_book_depth(self, bids: List[Tuple[float, float]], 
                                 asks: List[Tuple[float, float]]) -> Dict:
        """Analyze order book for potential hidden orders"""
        analysis = {
            'bid_concentration': 0.0,
            'ask_concentration': 0.0,
            'bid_gaps': [],
            'ask_gaps': [],
            'suspicious_levels': []
        }
        
        if not bids or not asks:
            return analysis
        
        # Analyze bid side
        bid_sizes = [size for _, size in bids]
        if bid_sizes:
            analysis['bid_concentration'] = max(bid_sizes) / sum(bid_sizes) if sum(bid_sizes) > 0 else 0
            analysis['bid_gaps'] = self._find_size_gaps(bid_sizes)
        
        # Analyze ask side
        ask_sizes = [size for _, size in asks]
        if ask_sizes:
            analysis['ask_concentration'] = max(ask_sizes) / sum(ask_sizes) if sum(ask_sizes) > 0 else 0
            analysis['ask_gaps'] = self._find_size_gaps(ask_sizes)
        
        # Find suspicious levels (potential hidden orders)
        if analysis['bid_concentration'] > 0.4 or analysis['ask_concentration'] > 0.4:
            analysis['suspicious_levels'].append({
                'type': 'high_concentration',
                'side': 'bid' if analysis['bid_concentration'] > 0.4 else 'ask'
            })
        
        return analysis
    
    def _find_size_gaps(self, sizes: List[float]) -> List[int]:
        """Find indices where there are unusual gaps in order sizes"""
        if len(sizes) < 2:
            return []
        
        gaps = []
        for i in range(len(sizes) - 1):
            if sizes[i] > 0 and sizes[i + 1] > 0:
                ratio = sizes[i] / sizes[i + 1]
                if ratio > 3.0 or ratio < 0.33:  # Significant size difference
                    gaps.append(i)
        
        return gaps
    
    def get_recent_detections(self, minutes: int = 5) -> List[IcebergSignal]:
        """Get recent iceberg detections"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [s for s in self.detected_icebergs if s.timestamp > cutoff]
    
    def clear_old_detections(self, hours: int = 24):
        """Clear old detections"""
        cutoff = datetime.now() - timedelta(hours=hours)
        self.detected_icebergs = [
            s for s in self.detected_icebergs if s.timestamp > cutoff
        ]
        
        logger.info(f"Cleared old detections, remaining: {len(self.detected_icebergs)}")
