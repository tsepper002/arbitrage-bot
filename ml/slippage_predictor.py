"""
Slippage Predictor - Real slippage prediction using online linear regression.
Learns from actual trades and predicts slippage % based on order size,
orderbook depth, and recent volatility.  Per-exchange-symbol calibration.
"""
import logging
import math
import time
from collections import defaultdict, deque
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_MAX_OBS = 2000


class SlippagePredictor:
    """Predicts execution slippage using online linear regression."""

    def __init__(self):
        # Per (symbol, exchange) calibration data
        # Each stores list of (x_vec, y) where x_vec = [order_size, inv_depth, 1.0]
        self._obs: Dict[str, deque] = defaultdict(lambda: deque(maxlen=_MAX_OBS))
        # Cached OLS coefficients per key: [beta_size, beta_inv_depth, intercept]
        self._coeff: Dict[str, list] = {}
        self.predictions_cache: Dict[str, tuple] = {}
        self.slippage_history: list = []
        logger.info("✅ SlippagePredictor initialized")

    # ----- data ingestion ----------------------------------------------------

    def observe(self, symbol: str, exchange: str,
                predicted_slippage: float, actual_slippage: float,
                order_size: float = 100.0, depth: float = 10000.0):
        """Learn from an actual trade execution."""
        try:
            key = f"{symbol}_{exchange}"
            inv_depth = 1.0 / max(depth, 1.0)
            x = [order_size, inv_depth, 1.0]
            self._obs[key].append((x, actual_slippage))
            # Refit coefficients periodically
            if len(self._obs[key]) % 10 == 0:
                self._fit(key)
        except Exception as e:
            logger.error(f"Error in observe: {e}")

    def record_actual(self, symbol: str, volume: float, actual_slippage: float):
        """Backward-compatible recording."""
        self.observe(symbol, 'default', 0.0, actual_slippage,
                     order_size=volume, depth=10000.0)

    # ----- prediction --------------------------------------------------------

    def predict(self, symbol_or_volume=None, exchange_or_orderbook=None,
                order_size_usdt: float = 100.0, orderbook_depth: Optional[float] = None,
                symbol: str = None, **kwargs) -> float:
        """Predict slippage %.

        New API: predict(symbol, exchange, order_size_usdt, orderbook_depth)
        Old API: predict(volume, orderbook, symbol) — backward compatible.
        """
        try:
            # Detect old-style call: predict(volume: float, orderbook: dict, symbol: str)
            if isinstance(symbol_or_volume, (int, float)):
                volume = float(symbol_or_volume)
                orderbook = exchange_or_orderbook if isinstance(exchange_or_orderbook, dict) else {}
                sym = symbol or 'BTC/USDT'
                return self._predict_from_orderbook(volume, orderbook, sym)

            # New-style call: predict(symbol, exchange, order_size_usdt, orderbook_depth)
            sym = symbol_or_volume or symbol or 'BTC/USDT'
            exch = exchange_or_orderbook if isinstance(exchange_or_orderbook, str) else 'default'
            depth = orderbook_depth or 10000.0

            key = f"{sym}_{exch}"
            if key in self._coeff:
                b = self._coeff[key]
                inv_depth = 1.0 / max(depth, 1.0)
                pred = b[0] * order_size_usdt + b[1] * inv_depth + b[2]
                return max(pred, 0.0001)

            # Fallback: simple model
            return 0.0001 + (order_size_usdt / max(depth, 1.0)) * 0.005

        except Exception as e:
            logger.error(f"Error predicting slippage: {e}")
            return 0.001

    def _predict_from_orderbook(self, volume: float, orderbook: dict, symbol: str) -> float:
        """Old-style prediction from orderbook dict."""
        cache_key = f"{symbol}_{volume}"
        if cache_key in self.predictions_cache:
            ct, cp = self.predictions_cache[cache_key]
            if time.time() - ct < 30:
                return cp

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        if not bids and not asks:
            return 0.001

        total_liq = (sum(float(b[1]) for b in bids[:10]) +
                     sum(float(a[1]) for a in asks[:10]))
        if total_liq == 0:
            slippage = 0.002
        else:
            ratio = min(volume / total_liq, 1.0)
            slippage = 0.0001 + ratio * 0.005

        # Blend with learned model if available
        key = f"{symbol}_default"
        if key in self._coeff:
            b = self._coeff[key]
            inv_depth = 1.0 / max(total_liq, 1.0)
            learned = b[0] * volume + b[1] * inv_depth + b[2]
            slippage = 0.5 * slippage + 0.5 * max(learned, 0.0)

        self.predictions_cache[cache_key] = (time.time(), slippage)
        return slippage

    # ----- OLS fitting -------------------------------------------------------

    def _fit(self, key: str):
        """Fit OLS: y = b0*x0 + b1*x1 + b2  (3 coefficients via normal equations)."""
        try:
            obs = list(self._obs[key])
            n = len(obs)
            if n < 5:
                return
            k = 3  # number of coefficients
            # Build X^T X and X^T y
            xtx = [[0.0] * k for _ in range(k)]
            xty = [0.0] * k
            for x, y in obs:
                for i in range(k):
                    xty[i] += x[i] * y
                    for j in range(k):
                        xtx[i][j] += x[i] * x[j]

            # Solve via Cramer / simple 3x3 inverse
            coeff = self._solve_3x3(xtx, xty)
            if coeff is not None:
                self._coeff[key] = coeff
        except Exception as e:
            logger.error(f"Error fitting OLS for {key}: {e}")

    @staticmethod
    def _solve_3x3(A, b):
        """Solve 3x3 linear system Ax=b using Cramer's rule."""
        def det3(m):
            return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                    - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                    + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))

        d = det3(A)
        if abs(d) < 1e-15:
            return None
        result = []
        for col in range(3):
            temp = [row[:] for row in A]
            for row in range(3):
                temp[row][col] = b[row]
            result.append(det3(temp) / d)
        return result


def get_slippage_predictor():
    """Factory function"""
    return SlippagePredictor()
