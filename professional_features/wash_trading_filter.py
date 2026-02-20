"""
Wash Trading Filter
Detects and filters fake volume and self-trading patterns
"""
import logging
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a trade for analysis"""
    timestamp: datetime
    price: float
    size: float
    buyer_id: Optional[str]
    seller_id: Optional[str]
    

@dataclass
class WashTradingAlert:
    """Alert for suspected wash trading"""
    timestamp: datetime
    symbol: str
    pattern_type: str
    confidence: float
    evidence: List[str]
    fake_volume: float


class WashTradingFilter:
    """Detects and filters wash trading activities"""
    
    def __init__(self, 
                 self_trade_window_ms: int = 1000,
                 price_tolerance: float = 0.0001,
                 min_confidence: float = 0.6):
        self.self_trade_window_ms = self_trade_window_ms
        self.price_tolerance = price_tolerance
        self.min_confidence = min_confidence
        
        self.trade_history: Dict[str, List[TradeRecord]] = defaultdict(list)
        self.alerts: List[WashTradingAlert] = []
        self.suspicious_pairs: Set[Tuple[str, str]] = set()
        
        logger.info(f"WashTradingFilter initialized: window={self_trade_window_ms}ms")
    
    def add_trade(self, symbol: str, price: float, size: float,
                  buyer_id: Optional[str] = None, 
                  seller_id: Optional[str] = None):
        """Add trade for analysis"""
        record = TradeRecord(
            timestamp=datetime.now(),
            price=price,
            size=size,
            buyer_id=buyer_id,
            seller_id=seller_id
        )
        
        self.trade_history[symbol].append(record)
        
        # Clean old trades (keep 1 hour)
        cutoff = datetime.now() - timedelta(hours=1)
        self.trade_history[symbol] = [
            t for t in self.trade_history[symbol] if t.timestamp > cutoff
        ]
    
    def detect_wash_trading(self, symbol: str) -> List[WashTradingAlert]:
        """Detect wash trading patterns"""
        if symbol not in self.trade_history:
            return []
        
        trades = self.trade_history[symbol]
        if len(trades) < 10:
            return []
        
        alerts = []
        
        # Pattern 1: Self-trading (same trader on both sides)
        self_trade_alert = self._detect_self_trading(symbol, trades)
        if self_trade_alert:
            alerts.append(self_trade_alert)
        
        # Pattern 2: Ping-pong trading (back and forth between two traders)
        pingpong_alert = self._detect_pingpong_trading(symbol, trades)
        if pingpong_alert:
            alerts.append(pingpong_alert)
        
        # Pattern 3: Volume spikes with no price movement
        volume_alert = self._detect_fake_volume(symbol, trades)
        if volume_alert:
            alerts.append(volume_alert)
        
        # Store alerts
        self.alerts.extend(alerts)
        
        return alerts
    
    def _detect_self_trading(self, symbol: str, trades: List[TradeRecord]) -> Optional[WashTradingAlert]:
        """Detect self-trading (same entity on both sides)"""
        self_trades = []
        
        for trade in trades:
            if trade.buyer_id and trade.seller_id and trade.buyer_id == trade.seller_id:
                self_trades.append(trade)
        
        if not self_trades:
            return None
        
        fake_volume = sum(t.size for t in self_trades)
        total_volume = sum(t.size for t in trades)
        
        if fake_volume / total_volume < 0.05:  # Less than 5%
            return None
        
        confidence = min(1.0, fake_volume / total_volume * 2)
        
        evidence = [
            f"Found {len(self_trades)} self-trades",
            f"Fake volume: {fake_volume:.2f} ({fake_volume/total_volume:.1%} of total)"
        ]
        
        logger.warning(f"Self-trading detected on {symbol}: {len(self_trades)} trades, "
                      f"{fake_volume:.2f} fake volume")
        
        return WashTradingAlert(
            timestamp=datetime.now(),
            symbol=symbol,
            pattern_type='self_trading',
            confidence=confidence,
            evidence=evidence,
            fake_volume=fake_volume
        )
    
    def _detect_pingpong_trading(self, symbol: str, trades: List[TradeRecord]) -> Optional[WashTradingAlert]:
        """Detect ping-pong trading between two entities"""
        if len(trades) < 20:
            return None
        
        # Look for repeated back-and-forth patterns
        trader_pairs = defaultdict(int)
        consecutive_pairs = 0
        
        for i in range(len(trades) - 1):
            t1, t2 = trades[i], trades[i + 1]
            
            if not (t1.buyer_id and t1.seller_id and t2.buyer_id and t2.seller_id):
                continue
            
            # Check if traders swap roles
            if (t1.buyer_id == t2.seller_id and t1.seller_id == t2.buyer_id):
                pair = tuple(sorted([t1.buyer_id, t1.seller_id]))
                trader_pairs[pair] += 1
                consecutive_pairs += 1
            else:
                consecutive_pairs = 0
        
        if not trader_pairs:
            return None
        
        # Find most suspicious pair
        max_swaps = max(trader_pairs.values())
        
        if max_swaps < 5:  # Need at least 5 swaps
            return None
        
        confidence = min(1.0, max_swaps / 10)
        
        if confidence < self.min_confidence:
            return None
        
        # Estimate fake volume from ping-pong trades
        fake_volume = sum(t.size for t in trades[-max_swaps * 2:])
        
        evidence = [
            f"Found {max_swaps} ping-pong swaps",
            f"Suspicious trader pairs: {len(trader_pairs)}",
            f"Estimated fake volume: {fake_volume:.2f}"
        ]
        
        logger.warning(f"Ping-pong trading detected on {symbol}: {max_swaps} swaps")
        
        return WashTradingAlert(
            timestamp=datetime.now(),
            symbol=symbol,
            pattern_type='pingpong',
            confidence=confidence,
            evidence=evidence,
            fake_volume=fake_volume
        )
    
    def _detect_fake_volume(self, symbol: str, trades: List[TradeRecord]) -> Optional[WashTradingAlert]:
        """Detect fake volume (high volume with minimal price movement)"""
        if len(trades) < 30:
            return None
        
        # Analyze recent trades
        recent = trades[-30:]
        
        prices = [t.price for t in recent]
        volumes = [t.size for t in recent]
        
        price_range = max(prices) - min(prices)
        avg_price = np.mean(prices)
        total_volume = sum(volumes)
        
        # Calculate price movement relative to volume
        price_volatility = price_range / avg_price if avg_price > 0 else 0
        
        # Suspicious if high volume but low price movement
        if price_volatility < 0.001 and total_volume > np.median(volumes) * 20:
            confidence = min(1.0, (0.001 - price_volatility) / 0.001)
            
            if confidence < self.min_confidence:
                return None
            
            evidence = [
                f"High volume ({total_volume:.2f}) with minimal price movement",
                f"Price volatility: {price_volatility:.4%}",
                f"Volume spike: {total_volume / np.median(volumes):.1f}x median"
            ]
            
            logger.warning(f"Fake volume detected on {symbol}: {total_volume:.2f} volume, "
                          f"{price_volatility:.4%} volatility")
            
            return WashTradingAlert(
                timestamp=datetime.now(),
                symbol=symbol,
                pattern_type='fake_volume',
                confidence=confidence,
                evidence=evidence,
                fake_volume=total_volume * 0.5  # Estimate 50% fake
            )
        
        return None
    
    def calculate_real_volume(self, symbol: str, time_window_minutes: int = 15) -> float:
        """Calculate estimated real volume (excluding wash trades)"""
        if symbol not in self.trade_history:
            return 0.0
        
        cutoff = datetime.now() - timedelta(minutes=time_window_minutes)
        recent_trades = [t for t in self.trade_history[symbol] if t.timestamp > cutoff]
        
        if not recent_trades:
            return 0.0
        
        total_volume = sum(t.size for t in recent_trades)
        
        # Detect and subtract fake volume
        alerts = self.detect_wash_trading(symbol)
        fake_volume = sum(a.fake_volume for a in alerts)
        
        real_volume = max(0, total_volume - fake_volume)
        
        return real_volume
    
    def get_statistics(self) -> Dict:
        """Get filtering statistics"""
        if not self.alerts:
            return {
                'total_alerts': 0,
                'by_type': {},
                'total_fake_volume': 0.0,
                'avg_confidence': 0.0
            }
        
        by_type = defaultdict(int)
        confidences = []
        
        for alert in self.alerts:
            by_type[alert.pattern_type] += 1
            confidences.append(alert.confidence)
        
        return {
            'total_alerts': len(self.alerts),
            'by_type': dict(by_type),
            'total_fake_volume': sum(a.fake_volume for a in self.alerts),
            'avg_confidence': np.mean(confidences),
            'suspicious_pairs': len(self.suspicious_pairs)
        }
    
    def is_suspicious_trade(self, symbol: str, price: float, size: float) -> Tuple[bool, float]:
        """Check if a trade is suspicious"""
        # Get recent alerts for this symbol
        recent_cutoff = datetime.now() - timedelta(minutes=5)
        recent_alerts = [a for a in self.alerts 
                        if a.symbol == symbol and a.timestamp > recent_cutoff]
        
        if not recent_alerts:
            return False, 0.0
        
        # Calculate suspicion score
        avg_confidence = np.mean([a.confidence for a in recent_alerts])
        
        return avg_confidence > 0.7, avg_confidence
