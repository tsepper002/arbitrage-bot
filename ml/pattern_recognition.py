"""
Pattern Recognition Module for Technical Analysis

Recognizes chart patterns, candlestick patterns, and technical indicators
for trading signal generation.
"""

import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Chart pattern types"""
    HEAD_AND_SHOULDERS = "head_and_shoulders"
    INVERSE_HEAD_AND_SHOULDERS = "inverse_head_and_shoulders"
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    TRIPLE_TOP = "triple_top"
    TRIPLE_BOTTOM = "triple_bottom"
    ASCENDING_TRIANGLE = "ascending_triangle"
    DESCENDING_TRIANGLE = "descending_triangle"
    SYMMETRICAL_TRIANGLE = "symmetrical_triangle"
    RISING_WEDGE = "rising_wedge"
    FALLING_WEDGE = "falling_wedge"
    FLAG = "flag"
    PENNANT = "pennant"


class CandlestickPattern(Enum):
    """Candlestick pattern types"""
    DOJI = "doji"
    HAMMER = "hammer"
    SHOOTING_STAR = "shooting_star"
    ENGULFING_BULLISH = "engulfing_bullish"
    ENGULFING_BEARISH = "engulfing_bearish"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"
    THREE_WHITE_SOLDIERS = "three_white_soldiers"
    THREE_BLACK_CROWS = "three_black_crows"


@dataclass
class Pattern:
    """Pattern detection result"""
    type: str
    confidence: float
    signal: str  # 'buy', 'sell', or 'neutral'
    start_idx: int
    end_idx: int
    metadata: Dict


class PatternRecognition:
    """
    Advanced pattern recognition for technical analysis.
    
    Features:
    - Support/resistance detection
    - Chart pattern recognition (head & shoulders, triangles, wedges, etc.)
    - Candlestick pattern detection
    - Technical indicators (RSI, MACD, Bollinger Bands)
    - Trend detection with strength measurement
    """
    
    def __init__(self, min_pattern_bars: int = 5, confidence_threshold: float = 0.6):
        """
        Initialize pattern recognition.
        
        Args:
            min_pattern_bars: Minimum bars for pattern formation
            confidence_threshold: Minimum confidence for pattern signals
        """
        self.logger = logging.getLogger(__name__)
        self.min_pattern_bars = min_pattern_bars
        self.confidence_threshold = confidence_threshold
        self.detected_patterns = []
    
    def detect_support_resistance(self, prices: List[float], threshold: float = 0.02) -> Dict:
        """
        Detect support and resistance levels using pivot points.
        
        Args:
            prices: List of prices
            threshold: Price similarity threshold
            
        Returns:
            Dictionary with support and resistance levels
        """
        if len(prices) < 3:
            return {'support': [], 'resistance': []}
        
        support = []
        resistance = []
        
        # Find local minima and maxima
        for i in range(2, len(prices) - 2):
            # Check if it's a local minimum (support)
            if (prices[i] < prices[i-1] and prices[i] < prices[i-2] and
                prices[i] < prices[i+1] and prices[i] < prices[i+2]):
                support.append(prices[i])
            
            # Check if it's a local maximum (resistance)
            elif (prices[i] > prices[i-1] and prices[i] > prices[i-2] and
                  prices[i] > prices[i+1] and prices[i] > prices[i+2]):
                resistance.append(prices[i])
        
        # Cluster nearby levels
        support = self._cluster_levels(support, threshold)
        resistance = self._cluster_levels(resistance, threshold)
        
        return {
            'support': sorted(support),
            'resistance': sorted(resistance, reverse=True)
        }
    
    def _cluster_levels(self, levels: List[float], threshold: float) -> List[float]:
        """Cluster nearby price levels"""
        if not levels:
            return []
        
        clustered = []
        levels_sorted = sorted(levels)
        current_cluster = [levels_sorted[0]]
        
        for level in levels_sorted[1:]:
            if abs(level - np.mean(current_cluster)) / np.mean(current_cluster) < threshold:
                current_cluster.append(level)
            else:
                clustered.append(np.mean(current_cluster))
                current_cluster = [level]
        
        clustered.append(np.mean(current_cluster))
        return clustered
    
    def detect_trend(self, prices: List[float]) -> Tuple[str, float]:
        """
        Detect trend direction and strength.
        
        Returns:
            Tuple of (direction, strength) where direction is 'uptrend', 'downtrend', or 'sideways'
        """
        if len(prices) < 10:
            return 'sideways', 0.0
        
        # Linear regression
        x = np.arange(len(prices))
        y = np.array(prices)
        slope, intercept = np.polyfit(x, y, 1)
        
        # Calculate R-squared
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Normalize slope to percentage
        slope_pct = (slope * len(prices)) / np.mean(prices) if np.mean(prices) != 0 else 0
        
        # Determine direction
        if r_squared > 0.6 and slope_pct > 0.02:
            return 'uptrend', r_squared
        elif r_squared > 0.6 and slope_pct < -0.02:
            return 'downtrend', r_squared
        else:
            return 'sideways', r_squared
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0
        
        changes = np.diff(prices)
        gains = np.where(changes > 0, changes, 0)
        losses = np.where(changes < 0, -changes, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices: List[float], 
                       fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """Calculate MACD indicator"""
        if len(prices) < slow + signal:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        # Calculate EMAs
        ema_fast = self._ema(prices, fast)
        ema_slow = self._ema(prices, slow)
        
        macd_line = ema_fast - ema_slow
        
        # Calculate signal line (EMA of MACD)
        macd_values = []
        for i in range(len(prices)):
            if i >= slow - 1:
                macd_values.append(self._ema(prices[:i+1], fast) - self._ema(prices[:i+1], slow))
        
        if len(macd_values) >= signal:
            signal_line = self._ema(macd_values, signal)
        else:
            signal_line = 0
        
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    def _ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return np.mean(prices)
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def calculate_bollinger_bands(self, prices: List[float], 
                                   period: int = 20, std_dev: int = 2) -> Dict:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return {'upper': 0, 'middle': 0, 'lower': 0}
        
        recent_prices = prices[-period:]
        middle = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'width': upper - lower
        }
    
    def detect_head_and_shoulders(self, prices: List[float]) -> Optional[Pattern]:
        """Detect head and shoulders pattern"""
        if len(prices) < 7:
            return None
        
        # Find peaks
        peaks = []
        for i in range(2, len(prices) - 2):
            if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                peaks.append((i, prices[i]))
        
        if len(peaks) < 3:
            return None
        
        # Check for H&S pattern: left shoulder < head > right shoulder
        for i in range(len(peaks) - 2):
            left = peaks[i][1]
            head = peaks[i+1][1]
            right = peaks[i+2][1]
            
            # Head should be highest
            if head > left and head > right:
                # Shoulders should be similar
                if abs(left - right) / left < 0.05:
                    return Pattern(
                        type=PatternType.HEAD_AND_SHOULDERS.value,
                        confidence=0.8,
                        signal='sell',
                        start_idx=peaks[i][0],
                        end_idx=peaks[i+2][0],
                        metadata={'left_shoulder': left, 'head': head, 'right_shoulder': right}
                    )
        
        return None
    
    def detect_double_top(self, prices: List[float]) -> Optional[Pattern]:
        """Detect double top pattern"""
        if len(prices) < 5:
            return None
        
        # Find peaks
        peaks = []
        for i in range(2, len(prices) - 2):
            if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                peaks.append((i, prices[i]))
        
        if len(peaks) < 2:
            return None
        
        # Check for double top: two similar peaks
        for i in range(len(peaks) - 1):
            peak1 = peaks[i][1]
            peak2 = peaks[i+1][1]
            
            if abs(peak1 - peak2) / peak1 < 0.02:  # Within 2%
                return Pattern(
                    type=PatternType.DOUBLE_TOP.value,
                    confidence=0.75,
                    signal='sell',
                    start_idx=peaks[i][0],
                    end_idx=peaks[i+1][0],
                    metadata={'peak1': peak1, 'peak2': peak2}
                )
        
        return None
    
    def find_all_patterns(self, prices: List[float]) -> List[Pattern]:
        """Find all recognizable patterns"""
        patterns = []
        
        # Chart patterns
        hs = self.detect_head_and_shoulders(prices)
        if hs:
            patterns.append(hs)
        
        dt = self.detect_double_top(prices)
        if dt:
            patterns.append(dt)
        
        # Filter by confidence
        patterns = [p for p in patterns if p.confidence >= self.confidence_threshold]
        
        self.detected_patterns = patterns
        return patterns
    
    def get_trading_signals(self, prices: List[float]) -> Dict:
        """
        Generate comprehensive trading signals from patterns and indicators.
        
        Returns:
            Dictionary with signals and confidence
        """
        if len(prices) < 20:
            return {'signal': 'neutral', 'confidence': 0, 'indicators': {}}
        
        # Calculate indicators
        rsi = self.calculate_rsi(prices)
        macd = self.calculate_macd(prices)
        bb = self.calculate_bollinger_bands(prices)
        trend, trend_strength = self.detect_trend(prices)
        sr_levels = self.detect_support_resistance(prices)
        patterns = self.find_all_patterns(prices)
        
        # Aggregate signals
        signals = []
        
        # RSI signals
        if rsi < 30:
            signals.append(('buy', 0.7))
        elif rsi > 70:
            signals.append(('sell', 0.7))
        
        # MACD signals
        if macd['histogram'] > 0:
            signals.append(('buy', 0.6))
        else:
            signals.append(('sell', 0.6))
        
        # Bollinger Bands
        current_price = prices[-1]
        if current_price < bb['lower']:
            signals.append(('buy', 0.65))
        elif current_price > bb['upper']:
            signals.append(('sell', 0.65))
        
        # Pattern signals
        for pattern in patterns:
            if pattern.signal in ['buy', 'sell']:
                signals.append((pattern.signal, pattern.confidence))
        
        # Aggregate
        if not signals:
            final_signal = 'neutral'
            confidence = 0
        else:
            buy_conf = sum(conf for sig, conf in signals if sig == 'buy')
            sell_conf = sum(conf for sig, conf in signals if sig == 'sell')
            
            if buy_conf > sell_conf:
                final_signal = 'buy'
                confidence = buy_conf / len(signals)
            elif sell_conf > buy_conf:
                final_signal = 'sell'
                confidence = sell_conf / len(signals)
            else:
                final_signal = 'neutral'
                confidence = 0.5
        
        return {
            'signal': final_signal,
            'confidence': confidence,
            'indicators': {
                'rsi': rsi,
                'macd': macd,
                'bollinger_bands': bb,
                'trend': trend,
                'trend_strength': trend_strength,
                'support_levels': sr_levels['support'][:3],
                'resistance_levels': sr_levels['resistance'][:3]
            },
            'patterns': [{'type': p.type, 'confidence': p.confidence, 'signal': p.signal} 
                        for p in patterns]
        }
