"""
ML Spread Predictor - Real spread prediction using EWMA + linear trend.
Uses circular buffer of observations and manual least-squares regression.
"""
import logging
import math
import time
from collections import deque
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_BUFFER_SIZE = 1000
_EWMA_SPAN = 50


class MLSpreadPredictor:
    """Predicts spreads using EWMA + linear trend with manual least-squares."""

    def __init__(self):
        self.buffers: Dict[str, deque] = {}          # symbol -> deque of (timestamp, spread)
        self.coefficients: Dict[str, tuple] = {}      # symbol -> (slope, intercept)
        self.ewma_values: Dict[str, float] = {}       # symbol -> current EWMA
        self.predictions_cache: Dict[str, tuple] = {}
        self.is_trained = False
        self._alpha = 2.0 / (_EWMA_SPAN + 1)
        logger.info("✅ MLSpreadPredictor initialized")

    # ----- core API ----------------------------------------------------------

    def observe(self, symbol: str, spread: float, timestamp: float = None):
        """Record a spread observation into the circular buffer."""
        try:
            ts = timestamp or time.time()
            if symbol not in self.buffers:
                self.buffers[symbol] = deque(maxlen=_BUFFER_SIZE)
                self.ewma_values[symbol] = spread
            buf = self.buffers[symbol]
            buf.append((ts, spread))
            # Update EWMA incrementally
            self.ewma_values[symbol] = (
                self._alpha * spread + (1 - self._alpha) * self.ewma_values[symbol]
            )
        except Exception as e:
            logger.error(f"Error in observe: {e}")

    def predict(self, symbol: str, features: Optional[Dict] = None) -> float:
        """Predict next spread using EWMA + linear trend.

        Backward-compatible: accepts optional features dict.
        """
        try:
            # Cache check
            if symbol in self.predictions_cache:
                cached_time, cached_pred = self.predictions_cache[symbol]
                if time.time() - cached_time < 10:
                    return cached_pred

            # Fallback when no observations yet
            if symbol not in self.buffers or len(self.buffers[symbol]) < 2:
                default = 0.001
                if features and isinstance(features, dict):
                    default = features.get('current_spread', 0.001) * 1.1
                return default

            ewma = self.ewma_values.get(symbol, 0.001)
            trend = 0.0
            if symbol in self.coefficients:
                slope, _ = self.coefficients[symbol]
                trend = slope  # one-step-ahead trend adjustment

            prediction = max(ewma + trend, 0.0)
            self.predictions_cache[symbol] = (time.time(), prediction)
            return prediction
        except Exception as e:
            logger.error(f"Error predicting spread: {e}")
            return 0.001

    def get_confidence(self, symbol: str) -> float:
        """Confidence [0-1] based on data quantity and stability."""
        try:
            if symbol not in self.buffers:
                return 0.0
            buf = self.buffers[symbol]
            n = len(buf)
            quantity_score = min(n / 200.0, 1.0)  # full confidence at 200 pts

            if n < 10:
                return quantity_score * 0.3

            spreads = [s for _, s in buf]
            mean = sum(spreads) / n
            var = sum((s - mean) ** 2 for s in spreads) / n
            std = math.sqrt(var) if var > 0 else 1e-12
            cv = std / abs(mean) if abs(mean) > 1e-12 else 1.0
            stability_score = max(0.0, 1.0 - cv)

            return round(min(quantity_score * 0.6 + stability_score * 0.4, 1.0), 4)
        except Exception as e:
            logger.error(f"Error computing confidence: {e}")
            return 0.0

    def train(self, historical_data: Optional[List[Dict]] = None):
        """Fit linear regression coefficients per symbol using least-squares.

        Can also be called with historical_data list[dict] for bulk loading.
        """
        try:
            if historical_data:
                for item in historical_data:
                    sym = item.get('symbol', 'UNKNOWN')
                    spread = item.get('spread', 0.0)
                    ts = item.get('timestamp', time.time())
                    self.observe(sym, spread, ts)

            for symbol, buf in self.buffers.items():
                n = len(buf)
                if n < 10:
                    continue
                self.coefficients[symbol] = self._fit_ols(buf)

            self.is_trained = True
            logger.info("✅ MLSpreadPredictor training complete (%d symbols)", len(self.coefficients))
        except Exception as e:
            logger.error(f"Error training model: {e}")

    # ----- backward-compat aliases ------------------------------------------

    def update(self, symbol: str, actual_spread: float):
        """Backward-compatible alias for observe."""
        self.observe(symbol, actual_spread)

    # ----- internals ---------------------------------------------------------

    @staticmethod
    def _fit_ols(buf: deque) -> tuple:
        """Manual ordinary least-squares on (index, spread) pairs. Returns (slope, intercept)."""
        n = len(buf)
        sx = sy = sxy = sx2 = 0.0
        for i, (_, spread) in enumerate(buf):
            sx += i
            sy += spread
            sxy += i * spread
            sx2 += i * i
        denom = n * sx2 - sx * sx
        if abs(denom) < 1e-15:
            return (0.0, sy / n if n else 0.0)
        slope = (n * sxy - sx * sy) / denom
        intercept = (sy - slope * sx) / n
        return (slope, intercept)


def get_ml_spread_predictor():
    """Factory function"""
    return MLSpreadPredictor()
