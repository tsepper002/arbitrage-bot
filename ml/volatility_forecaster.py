"""
Volatility Forecaster - Real EWMA volatility forecasting.
Uses exponentially weighted moving average of squared returns (RiskMetrics λ=0.94).
"""
import logging
import math
import time
from collections import deque
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_MAX_HISTORY = 2000
_LAMBDA = 0.94
_PERCENTILE_THRESHOLDS = (25, 75, 95)  # LOW / NORMAL / HIGH / EXTREME


class VolatilityForecaster:
    """Forecasts volatility using EWMA (RiskMetrics approach)."""

    def __init__(self, lookback_period: int = 100):
        self.lookback_period = lookback_period
        self.price_history: Dict[str, deque] = {}       # symbol -> deque of (ts, price)
        self.return_history: Dict[str, deque] = {}       # symbol -> deque of log-returns
        self.ewma_var: Dict[str, float] = {}             # symbol -> current EWMA variance
        self.vol_samples: Dict[str, deque] = {}          # for regime percentiles
        self.volatility_forecasts: Dict[str, tuple] = {}
        logger.info("✅ VolatilityForecaster initialized")

    # ----- data ingestion ----------------------------------------------------

    def observe(self, symbol: str, price: float, timestamp: float = None):
        """Record a price observation and update EWMA variance."""
        try:
            ts = timestamp or time.time()
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=_MAX_HISTORY)
                self.return_history[symbol] = deque(maxlen=_MAX_HISTORY)
                self.vol_samples[symbol] = deque(maxlen=_MAX_HISTORY)

            prices = self.price_history[symbol]
            if prices and prices[-1][1] > 0 and price > 0:
                log_ret = math.log(price / prices[-1][1])
                self.return_history[symbol].append(log_ret)
                # EWMA variance update
                if symbol in self.ewma_var:
                    self.ewma_var[symbol] = (
                        _LAMBDA * self.ewma_var[symbol] + (1 - _LAMBDA) * log_ret * log_ret
                    )
                else:
                    self.ewma_var[symbol] = log_ret * log_ret
                self.vol_samples[symbol].append(math.sqrt(self.ewma_var[symbol]))

            prices.append((ts, price))
        except Exception as e:
            logger.error(f"Error in observe: {e}")

    # ----- forecasting -------------------------------------------------------

    def forecast(self, symbol: str, horizon_minutes: float = 5,
                 current_price: Optional[float] = None, horizon: Optional[int] = None) -> float:
        """Forecast volatility for a future horizon using EWMA variance.

        Backward-compatible: accepts old-style (symbol, current_price, horizon) too.
        """
        try:
            # Backward compat: old API passed current_price as second positional arg
            if current_price is not None:
                self.observe(symbol, current_price)
            if horizon is not None:
                horizon_minutes = horizon  # treat old horizon as minutes

            # Cache
            cache_key = f"{symbol}_{horizon_minutes}"
            if cache_key in self.volatility_forecasts:
                ct, cf = self.volatility_forecasts[cache_key]
                if time.time() - ct < 60:
                    return cf

            if symbol not in self.ewma_var:
                return 0.01

            # Annualised sqrt-of-time scaling (assume 1-min base interval)
            base_vol = math.sqrt(self.ewma_var[symbol])
            forecast_val = base_vol * math.sqrt(max(horizon_minutes, 1))

            self.volatility_forecasts[cache_key] = (time.time(), forecast_val)
            return forecast_val
        except Exception as e:
            logger.error(f"Error forecasting volatility: {e}")
            return 0.01

    def get_current_volatility(self, symbol: str) -> float:
        """Get current realized volatility (annualised std of recent returns)."""
        try:
            if symbol not in self.return_history or len(self.return_history[symbol]) < 5:
                if symbol in self.ewma_var:
                    return math.sqrt(self.ewma_var[symbol])
                return 0.01
            rets = list(self.return_history[symbol])
            n = len(rets)
            mean = sum(rets) / n
            var = sum((r - mean) ** 2 for r in rets) / n
            return math.sqrt(var) if var > 0 else 1e-8
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 0.01

    def get_regime(self, symbol: str) -> str:
        """Classify current volatility regime: LOW / NORMAL / HIGH / EXTREME."""
        try:
            if symbol not in self.vol_samples or len(self.vol_samples[symbol]) < 20:
                return 'NORMAL'
            samples = sorted(self.vol_samples[symbol])
            current = samples[-1]
            n = len(samples)
            p25 = samples[int(n * 0.25)]
            p75 = samples[int(n * 0.75)]
            p95 = samples[min(int(n * 0.95), n - 1)]
            if current <= p25:
                return 'LOW'
            elif current <= p75:
                return 'NORMAL'
            elif current <= p95:
                return 'HIGH'
            else:
                return 'EXTREME'
        except Exception as e:
            logger.error(f"Error determining regime: {e}")
            return 'NORMAL'


def get_volatility_forecaster():
    """Factory function"""
    return VolatilityForecaster()
