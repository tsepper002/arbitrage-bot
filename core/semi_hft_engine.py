"""
Semi-HFT Engine — Professional-grade execution layer for crypto arbitrage.

Implements the 7-stage semi-HFT plan:
  Stage 1: Infrastructure (latency tracking, auto-exclude slow exchanges)
  Stage 2: Architecture (per-symbol locks, event-driven triggers)
  Stage 3: Execution (predictive maker, early partial hedge, order slicing)
  Stage 4: Edge filtration (dynamic threshold 2.0, exchange pair scoring, vol regime)
  Stage 5: Strategies (lead-lag arbitrage, cross-exchange microstructure)
  Stage 6: Capital scaling (via CapitalManager)
  Stage 7: Risk controls (latency/slippage/fill-rate kill-switches)

Target: end-to-end latency ≤ 80-150ms, fill-rate ≥ 65%, net edge ≥ 0.08-0.15%
"""

import asyncio
import time
import math
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import settings

logger = logging.getLogger("semi_hft")


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class LatencyStats:
    """Per-exchange RTT statistics."""
    samples: deque = field(default_factory=lambda: deque(maxlen=100))
    ema_ms: float = 200.0  # EMA of round-trip time in ms
    EMA_ALPHA: float = 0.3

    def record(self, rtt_ms: float):
        rtt_ms = max(0.0, min(rtt_ms, 10000.0))  # Clamp absurd values
        self.samples.append(rtt_ms)
        self.ema_ms = self.EMA_ALPHA * rtt_ms + (1 - self.EMA_ALPHA) * self.ema_ms

    @property
    def p95(self) -> float:
        if len(self.samples) < 5:
            return self.ema_ms
        s = sorted(self.samples)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s) - 1)]

    @property
    def avg(self) -> float:
        if not self.samples:
            return self.ema_ms
        return sum(self.samples) / len(self.samples)


@dataclass
class FillStats:
    """Per-exchange fill rate tracking."""
    attempts: int = 0
    fills: int = 0
    partial_fills: int = 0

    @property
    def fill_rate(self) -> float:
        if self.attempts == 0:
            return 1.0
        return self.fills / self.attempts

    def record_attempt(self, filled: bool, partial: bool = False):
        self.attempts += 1
        if filled:
            self.fills += 1
        if partial:
            self.partial_fills += 1


@dataclass
class ExchangePairScore:
    """Quality scoring for a buy-exchange → sell-exchange pair."""
    wins: int = 0
    total: int = 0
    total_net_profit_pct: float = 0.0
    total_slippage_pct: float = 0.0
    total_latency_ms: float = 0.0

    @property
    def score(self) -> float:
        if self.total < 3:
            return 1.0  # Not enough data
        winrate = self.wins / self.total
        avg_profit = self.total_net_profit_pct / self.total
        avg_slip = self.total_slippage_pct / self.total if self.total > 0 else 0.01
        avg_latency = self.total_latency_ms / self.total if self.total > 0 else 200
        return winrate * max(avg_profit, 0.001) / (max(avg_slip, 0.01) * max(avg_latency, 1) * 0.001)

    def record(self, net_profit_pct: float, slippage_pct: float, latency_ms: float):
        self.total += 1
        self.total_net_profit_pct += net_profit_pct
        self.total_slippage_pct += slippage_pct
        self.total_latency_ms += latency_ms
        if net_profit_pct > 0:
            self.wins += 1


@dataclass
class OrderbookImbalance:
    """Tracks bid/ask imbalance for a symbol on an exchange."""
    bid_volume: float = 0.0
    ask_volume: float = 0.0

    @property
    def ratio(self) -> float:
        """Bid/ask imbalance ratio. >1 = buy pressure, <1 = sell pressure."""
        total = self.bid_volume + self.ask_volume
        if total < 1e-12:
            return 1.0
        return self.bid_volume / total

    @property
    def is_buy_heavy(self) -> bool:
        return self.ratio > 0.6

    @property
    def is_sell_heavy(self) -> bool:
        return self.ratio < 0.4


# ============================================================================
# VOLATILITY REGIME DETECTOR
# ============================================================================

class VolatilityRegime:
    """Detects market volatility regime: FLAT, TRENDING, PANIC."""

    FLAT_THRESHOLD = 0.3     # < 0.3% spread vol = flat
    PANIC_THRESHOLD = 2.0    # > 2.0% spread vol = panic

    def __init__(self):
        self._spread_samples: deque = deque(maxlen=200)
        self._regime = "FLAT"

    def update(self, spread_pct: float):
        self._spread_samples.append(abs(spread_pct))
        if len(self._spread_samples) < 10:
            return
        # Use standard deviation of recent spreads as volatility proxy
        avg = sum(self._spread_samples) / len(self._spread_samples)
        var = sum((s - avg) ** 2 for s in self._spread_samples) / len(self._spread_samples)
        std = math.sqrt(var) if var > 0 else 0
        if std > self.PANIC_THRESHOLD:
            self._regime = "PANIC"
        elif std > self.FLAT_THRESHOLD:
            self._regime = "TRENDING"
        else:
            self._regime = "FLAT"

    @property
    def regime(self) -> str:
        return self._regime

    @property
    def is_panic(self) -> bool:
        return self._regime == "PANIC"


# ============================================================================
# LEAD-LAG DETECTOR
# ============================================================================

class LeadLagDetector:
    """
    Detects which exchange leads price changes and which lags.
    The lagging exchange is where we can enter BEFORE it updates.
    """

    def __init__(self, window: int = 50):
        self._price_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window)
        )
        self._lead_scores: Dict[str, float] = {}

    def record_price(self, exchange: str, symbol: str, mid_price: float):
        key = f"{symbol}:{exchange}"
        self._price_history[key].append((time.time(), mid_price))

    def get_leader(self, symbol: str, exchanges: List[str]) -> Optional[str]:
        """Return the exchange that leads price changes for this symbol."""
        if len(exchanges) < 2:
            return None

        # Compare price change timestamps: which exchange moves first?
        change_leads: Dict[str, int] = defaultdict(int)
        for ex in exchanges:
            key = f"{symbol}:{ex}"
            hist = self._price_history.get(key)
            if not hist or len(hist) < 5:
                continue
            # Count how many times this exchange had the first price change
            for i in range(1, min(len(hist), 20)):
                if abs(hist[i][1] - hist[i - 1][1]) > 1e-8:
                    change_leads[ex] += 1

        if not change_leads:
            return None

        leader = max(change_leads, key=change_leads.get)
        return leader

    def get_lagger(self, symbol: str, exchanges: List[str]) -> Optional[str]:
        """Return the exchange that lags price changes (best entry)."""
        leader = self.get_leader(symbol, exchanges)
        if not leader:
            return None
        laggers = [ex for ex in exchanges if ex != leader]
        return laggers[0] if laggers else None


# ============================================================================
# SEMI-HFT ENGINE
# ============================================================================

class SemiHFTEngine:
    """
    Central semi-HFT coordinator. Integrates all 7 stages.

    Usage:
        hft = SemiHFTEngine()
        hft.record_latency("Binance", 45.0)
        hft.record_latency("MEXC", 62.0)

        # Before scanning:
        if hft.should_exclude_exchange("HTX"):
            skip HTX

        # Before executing:
        threshold = hft.dynamic_threshold_v2(total_fees, buy_ex, sell_ex)
        if spread < threshold:
            skip

        # Execution decisions:
        if hft.should_use_maker(symbol, buy_ex, spread_pct):
            use maker-first model
        else:
            use market-market

        # After trade:
        hft.record_trade_result(buy_ex, sell_ex, symbol, profit, slippage, latency)
    """

    # Stage 1: Latency thresholds
    MAX_RTT_MS = 450              # Exclude exchanges with RTT > 450ms
    MAX_ERROR_RATE = 0.03         # Exclude if > 3% error rate
    MAX_RTT_CLAMP_MS = 10000.0   # Clamp absurd RTT values (>10s)
    TIME_SYNC_INTERVAL_SEC = 30   # Resync time every 30s

    # Stage 2: Per-symbol locks (instead of global)
    # Event-driven: threshold for triggering rescan
    SPREAD_CHANGE_TRIGGER_PCT = 0.02  # Re-scan if spread changes by 0.02%

    # Stage 3: Maker model
    MAKER_MIN_FILL_PROBABILITY = 0.50  # Don't place maker if <50% fill prob
    EARLY_HEDGE_FILL_PCT = 30.0        # Start hedge at 30% fill (not 75%)
    ORDER_SLICE_COUNT = 3              # Split into 3 micro-orders
    # Fill probability weights (sum to 1.0)
    FILL_WEIGHT_IMBALANCE = 0.4        # Orderbook imbalance impact
    FILL_WEIGHT_HISTORY = 0.4          # Historical fill rate impact
    FILL_WEIGHT_DEPTH = 0.2            # Book depth impact

    # Stage 4: Dynamic threshold 2.0
    EXECUTION_FAILURE_BUFFER = 0.02    # +0.02% per 10% failure rate
    FAILURE_RATE_SCALE = 10            # Multiplier for failure rate → threshold
    P95_SLIPPAGE_WEIGHT = 0.5          # Use p95 slippage in threshold

    # Stage 7: Kill-switches
    KILL_SWITCH_COOLDOWN_SEC = 300     # 5 min cooldown after kill
    FILL_RATE_COOLDOWN_SEC = 600       # 10 min cooldown for fill-rate kill
    LATENCY_SPIKE_MS = 500             # Kill if latency spike > 500ms
    SLIPPAGE_SPIKE_PCT = 0.5           # Kill if slippage spike > 0.5%
    MIN_FILL_RATE_PCT = 40.0           # Auto-disable at fill-rate < 40%
    MAX_INVENTORY_SKEW_PCT = 60.0      # Max % of position on one side

    def __init__(self):
        # Stage 1: Latency tracking
        self._latency: Dict[str, LatencyStats] = defaultdict(LatencyStats)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._request_counts: Dict[str, int] = defaultdict(int)

        # Stage 2: Per-symbol locks
        self._symbol_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_spread: Dict[str, float] = {}  # symbol:pair -> last spread

        # Stage 3: Fill stats
        self._fill_stats: Dict[str, FillStats] = defaultdict(FillStats)

        # Stage 4: Exchange pair scoring
        self._pair_scores: Dict[str, ExchangePairScore] = defaultdict(ExchangePairScore)
        self._slippage_history: deque = deque(maxlen=500)

        # Stage 5: Lead-lag + microstructure
        self._lead_lag = LeadLagDetector()
        self._orderbook_imbalance: Dict[str, OrderbookImbalance] = {}

        # Volatility regime
        self._vol_regime = VolatilityRegime()

        # Stage 7: Risk state
        self._latency_kill_until: Dict[str, float] = {}
        self._slippage_kill_until: Dict[str, float] = {}
        self._fill_rate_kill_until: Dict[str, float] = {}
        self._exclusion_logged: Dict[str, bool] = {}  # Track logged exclusions (avoid spam)

        logger.info("🚀 Semi-HFT Engine initialized")

    # ------------------------------------------------------------------
    # STAGE 1: INFRASTRUCTURE — Latency + Exchange Health
    # ------------------------------------------------------------------

    def record_latency(self, exchange: str, rtt_ms: float):
        """Record a round-trip time measurement for an exchange."""
        self._latency[exchange].record(rtt_ms)
        self._request_counts[exchange] = self._request_counts.get(exchange, 0) + 1

    def record_error(self, exchange: str):
        """Record an API error for an exchange."""
        self._error_counts[exchange] = self._error_counts.get(exchange, 0) + 1
        self._request_counts[exchange] = self._request_counts.get(exchange, 0) + 1

    MIN_SAMPLES_FOR_EXCLUSION = 3  # Need at least N measurements before excluding

    def should_exclude_exchange(self, exchange: str) -> bool:
        """Check if exchange should be excluded due to latency or errors.
        
        Requires MIN_SAMPLES_FOR_EXCLUSION measurements before excluding
        (prevents one bad ping from permanently killing an exchange).
        Logs exclusion only once per exchange to avoid log spam.
        """
        now = time.time()

        # Check kill-switch timeouts
        if self._latency_kill_until.get(exchange, 0) > now:
            return True
        if self._slippage_kill_until.get(exchange, 0) > now:
            return True
        if self._fill_rate_kill_until.get(exchange, 0) > now:
            return True

        # Check latency (only after enough samples to be reliable)
        stats = self._latency.get(exchange)
        if stats and len(stats.samples) >= self.MIN_SAMPLES_FOR_EXCLUSION and stats.ema_ms > self.MAX_RTT_MS:
            if not self._exclusion_logged.get(exchange):
                logger.warning(f"⚡ {exchange} excluded: latency {stats.ema_ms:.0f}ms > {self.MAX_RTT_MS}ms (based on {len(stats.samples)} samples)")
                self._exclusion_logged[exchange] = True
            return True

        # Check error rate (only with enough data)
        reqs = self._request_counts.get(exchange, 0)
        errs = self._error_counts.get(exchange, 0)
        if reqs > 20 and (errs / reqs) > self.MAX_ERROR_RATE:
            if not self._exclusion_logged.get(exchange):
                logger.warning(f"⚡ {exchange} excluded: error rate {errs / reqs:.1%} > {self.MAX_ERROR_RATE:.0%}")
                self._exclusion_logged[exchange] = True
            return True

        # Exchange is healthy — clear any previous exclusion log
        if self._exclusion_logged.get(exchange):
            stats = self._latency.get(exchange)
            latency_str = f"{stats.ema_ms:.0f}ms" if stats else "unknown"
            samples = len(stats.samples) if stats else 0
            logger.info(f"✅ {exchange} recovered — latency {latency_str} ({samples} samples)")
            self._exclusion_logged[exchange] = False

        return False

    def get_exchange_latency_ms(self, exchange: str) -> float:
        """Get current latency EMA for an exchange."""
        stats = self._latency.get(exchange)
        return stats.ema_ms if stats else 200.0

    def get_top_exchanges(self, exchanges: List[str], n: int = 3) -> List[str]:
        """Return the N best exchanges by latency+stability, excluding bad ones."""
        valid = [ex for ex in exchanges if not self.should_exclude_exchange(ex)]
        valid.sort(key=lambda ex: self._latency.get(ex, LatencyStats()).ema_ms)
        return valid[:n]

    # ------------------------------------------------------------------
    # STAGE 2: PER-SYMBOL LOCKS + EVENT-DRIVEN
    # ------------------------------------------------------------------

    def get_symbol_lock(self, symbol: str) -> asyncio.Lock:
        """Get per-symbol lock (not global) for parallel trading."""
        return self._symbol_locks[symbol]

    def should_rescan(self, symbol: str, buy_ex: str, sell_ex: str,
                      current_spread_pct: float) -> bool:
        """Event-driven: should we rescan this pair?"""
        key = f"{symbol}:{buy_ex}->{sell_ex}"
        last = self._last_spread.get(key, 0)
        delta = abs(current_spread_pct - last)
        self._last_spread[key] = current_spread_pct
        return delta >= self.SPREAD_CHANGE_TRIGGER_PCT

    # ------------------------------------------------------------------
    # STAGE 3: EXECUTION — Predictive Maker + Early Hedge + Slicing
    # ------------------------------------------------------------------

    def predict_fill_probability(self, symbol: str, exchange: str,
                                 bids: List[Tuple[float, float]],
                                 asks: List[Tuple[float, float]],
                                 side: str = 'buy') -> float:
        """
        Predict probability of maker order being filled.

        Factors:
          - Orderbook imbalance (buy pressure helps buy fills)
          - Historical fill rate on this exchange
          - Depth at best level (more depth = harder to fill at same price)
        """
        # 1. Orderbook imbalance
        bid_vol = sum(s for _, s in bids[:5]) if bids else 0
        ask_vol = sum(s for _, s in asks[:5]) if asks else 0
        total_vol = bid_vol + ask_vol
        if total_vol < 1e-12:
            return 0.5

        if side == 'buy':
            # For buying: higher ask volume means more sellers → easier to fill
            imbalance_factor = ask_vol / total_vol
        else:
            imbalance_factor = bid_vol / total_vol

        # 2. Historical fill rate
        stats = self._fill_stats.get(exchange)
        hist_fill = stats.fill_rate if stats else 0.65

        # 3. Depth pressure (thinner book = easier to fill, denser = harder)
        best_depth = asks[0][1] if asks and side == 'buy' else (bids[0][1] if bids else 0)
        # Base factor 0.5 + inverse depth scaled by 100: thin book → ~1.0, deep book → ~0.5
        depth_factor = min(1.0, 0.5 + (1.0 / max(best_depth * 100, 1)))

        # Weighted combination (weights defined as class constants)
        prob = (self.FILL_WEIGHT_IMBALANCE * imbalance_factor +
                self.FILL_WEIGHT_HISTORY * hist_fill +
                self.FILL_WEIGHT_DEPTH * depth_factor)
        return max(0.0, min(1.0, prob))

    def should_use_maker(self, symbol: str, exchange: str,
                         bids: List[Tuple[float, float]],
                         asks: List[Tuple[float, float]],
                         spread_pct: float) -> bool:
        """Decide: maker-first or market-market based on fill probability."""
        if self._vol_regime.is_panic:
            return False  # In panic: no maker, go market immediately

        prob = self.predict_fill_probability(symbol, exchange, bids, asks, 'buy')
        if prob < self.MAKER_MIN_FILL_PROBABILITY:
            return False  # Low fill probability → market-market safer

        return True

    def get_early_hedge_pct(self) -> float:
        """Return the fill% threshold at which to start hedging."""
        return self.EARLY_HEDGE_FILL_PCT

    def compute_order_slices(self, total_qty: float, base_price: float,
                             spread: float, n_slices: int = 0) -> List[Tuple[float, float]]:
        """
        Split a single order into N micro-orders at different prices.

        Returns: list of (price, qty) tuples.
        """
        if n_slices <= 0:
            n_slices = self.ORDER_SLICE_COUNT
        if n_slices <= 1 or total_qty <= 0:
            return [(base_price, total_qty)]

        slices = []
        qty_per_slice = total_qty / n_slices
        for i in range(n_slices):
            # Price at 10%, 20%, 30% of spread above base
            offset_pct = (i + 1) / (n_slices + 1)
            price = base_price + spread * offset_pct
            slices.append((price, qty_per_slice))
        return slices

    def record_fill(self, exchange: str, filled: bool, partial: bool = False):
        """Record a fill attempt result."""
        self._fill_stats[exchange].record_attempt(filled, partial)

    # ------------------------------------------------------------------
    # STAGE 4: EDGE FILTRATION — Dynamic Threshold 2.0
    # ------------------------------------------------------------------

    def dynamic_threshold_v2(self, total_fee_pct: float,
                             buy_exchange: str, sell_exchange: str,
                             capital_manager=None) -> float:
        """
        Dynamic threshold 2.0 — aligned with top arb bots (CCXT/Barbotine):
            threshold = fees + level-specific cushion (from CapitalManager)

        TOP BOT PATTERN: Simple threshold = fees + small buffer.
        Previous version added p95_slippage + failure_rate + vol_regime on top,
        which inflated the threshold by 0.03-0.10% and blocked profitable trades.
        These are now DATA COLLECTION ONLY (logged, not added to threshold).
        """
        # Base threshold from CapitalManager: fees + cushion (0.008-0.015%)
        buy_lat = self.get_exchange_latency_ms(buy_exchange)
        sell_lat = self.get_exchange_latency_ms(sell_exchange)
        avg_latency = (buy_lat + sell_lat) / 2.0

        if capital_manager:
            base = capital_manager.dynamic_threshold(total_fee_pct, avg_latency)
        else:
            base = total_fee_pct + 0.015  # fallback: fees + 0.015% (Level 1 cushion)

        # --- DATA COLLECTION (advisory only, NOT added to threshold) ---

        # Track p95 slippage for monitoring
        if self._slippage_history:
            sorted_slip = sorted(self._slippage_history)
            p95_idx = max(0, int(len(sorted_slip) * 0.95) - 1)
            p95_slip = sorted_slip[min(p95_idx, len(sorted_slip) - 1)]
            logger.debug(f"p95 slippage: {p95_slip:.4f}% (monitoring only)")

        # Track failure rate for monitoring
        pair_key = f"{buy_exchange}->{sell_exchange}"
        pair_stats = self._pair_scores.get(pair_key)
        if pair_stats and pair_stats.total >= 5:
            failure_rate = 1.0 - (pair_stats.wins / pair_stats.total)
            logger.debug(f"Pair {pair_key} failure rate: {failure_rate:.1%} (monitoring only)")

        # ONLY in PANIC regime do we raise the threshold (market structure broken)
        # Note: this is the ONLY non-data addition — justified because PANIC means
        # orderbooks are unreliable and fills are unpredictable
        if self._vol_regime.regime == "PANIC":
            base += 0.05  # +0.05% in panic (reduced from 0.10%: still trades wide spreads)

        return base

    def record_slippage(self, slippage_pct: float):
        """Record actual slippage for p95 tracking."""
        self._slippage_history.append(abs(slippage_pct))

    # ------------------------------------------------------------------
    # STAGE 4: EXCHANGE PAIR SCORING
    # ------------------------------------------------------------------

    def record_pair_result(self, buy_ex: str, sell_ex: str,
                           net_profit_pct: float, slippage_pct: float,
                           latency_ms: float):
        """Record trade result for exchange pair scoring."""
        key = f"{buy_ex}->{sell_ex}"
        self._pair_scores[key].record(net_profit_pct, slippage_pct, latency_ms)

    def get_top_pairs(self, n: int = 2) -> List[str]:
        """Return top N exchange pairs by quality score."""
        if not self._pair_scores:
            return []
        scored = [(k, v.score) for k, v in self._pair_scores.items() if v.total >= 3]
        scored.sort(key=lambda x: -x[1])
        return [k for k, _ in scored[:n]]

    def is_top_pair(self, buy_ex: str, sell_ex: str) -> bool:
        """Check if this exchange pair is among the top scoring pairs."""
        # If not enough data, allow all pairs
        total_trades = sum(p.total for p in self._pair_scores.values())
        if total_trades < 20:
            return True  # Not enough data to filter yet
        key = f"{buy_ex}->{sell_ex}"
        top = self.get_top_pairs(n=4)  # Allow top 4 pairs
        return key in top or key not in self._pair_scores

    # ------------------------------------------------------------------
    # STAGE 5: LEAD-LAG + MICROSTRUCTURE
    # ------------------------------------------------------------------

    def update_orderbook_imbalance(self, symbol: str, exchange: str,
                                   bids: List[Tuple[float, float]],
                                   asks: List[Tuple[float, float]]):
        """Update orderbook imbalance for microstructure analysis."""
        key = f"{symbol}:{exchange}"
        bid_vol = sum(s for _, s in bids[:10]) if bids else 0
        ask_vol = sum(s for _, s in asks[:10]) if asks else 0
        self._orderbook_imbalance[key] = OrderbookImbalance(bid_vol, ask_vol)

    def get_imbalance(self, symbol: str, exchange: str) -> Optional[OrderbookImbalance]:
        """Get current orderbook imbalance for a symbol+exchange."""
        return self._orderbook_imbalance.get(f"{symbol}:{exchange}")

    def record_mid_price(self, exchange: str, symbol: str, mid_price: float):
        """Record mid price for lead-lag analysis."""
        self._lead_lag.record_price(exchange, symbol, mid_price)

    def get_price_leader(self, symbol: str, exchanges: List[str]) -> Optional[str]:
        """Get the exchange that typically leads price changes for this symbol."""
        return self._lead_lag.get_leader(symbol, exchanges)

    def is_lead_lag_opportunity(self, symbol: str, buy_ex: str, sell_ex: str,
                                exchanges: List[str]) -> bool:
        """
        Check if there's a lead-lag opportunity:
        If the buy exchange is the lagger (hasn't updated yet),
        and the sell exchange is the leader (already moved up),
        this is a favorable timing.
        """
        leader = self._lead_lag.get_leader(symbol, exchanges)
        if leader is None:
            return False  # Not enough data
        # Favorable: sell on leader (price already moved up), buy on lagger (still cheap)
        return sell_ex == leader and buy_ex != leader

    def update_volatility(self, spread_pct: float):
        """Feed spread data into volatility regime detector."""
        self._vol_regime.update(spread_pct)

    @property
    def volatility_regime(self) -> str:
        return self._vol_regime.regime

    # ------------------------------------------------------------------
    # STAGE 7: RISK CONTROLS — Kill-switches
    # ------------------------------------------------------------------

    def check_latency_kill(self, exchange: str) -> bool:
        """Check and trigger latency kill-switch if spike detected."""
        stats = self._latency.get(exchange)
        if not stats:
            return False
        if stats.ema_ms > self.LATENCY_SPIKE_MS:
            self._latency_kill_until[exchange] = time.time() + self.KILL_SWITCH_COOLDOWN_SEC
            logger.warning(
                f"🛑 LATENCY KILL: {exchange} disabled 5min "
                f"(latency {stats.ema_ms:.0f}ms > {self.LATENCY_SPIKE_MS}ms)"
            )
            return True
        return False

    def check_slippage_kill(self, exchange: str, slippage_pct: float) -> bool:
        """Check and trigger slippage kill-switch if spike detected."""
        if slippage_pct > self.SLIPPAGE_SPIKE_PCT:
            self._slippage_kill_until[exchange] = time.time() + self.KILL_SWITCH_COOLDOWN_SEC
            logger.warning(
                f"🛑 SLIPPAGE KILL: {exchange} disabled 5min "
                f"(slippage {slippage_pct:.3f}% > {self.SLIPPAGE_SPIKE_PCT}%)"
            )
            return True
        return False

    def check_fill_rate_kill(self, exchange: str) -> bool:
        """Check and trigger fill-rate kill-switch if rate too low."""
        stats = self._fill_stats.get(exchange)
        if not stats or stats.attempts < 10:
            return False
        rate = stats.fill_rate * 100
        if rate < self.MIN_FILL_RATE_PCT:
            self._fill_rate_kill_until[exchange] = time.time() + self.FILL_RATE_COOLDOWN_SEC
            logger.warning(
                f"🛑 FILL-RATE KILL: {exchange} disabled 10min "
                f"(fill rate {rate:.0f}% < {self.MIN_FILL_RATE_PCT}%)"
            )
            return True
        return False

    def check_inventory_skew(self, usdt_value: float, base_value: float) -> bool:
        """Check if inventory skew exceeds maximum allowed."""
        total = usdt_value + base_value
        if total < 1e-8:
            return False
        max_side = max(usdt_value, base_value)
        skew_pct = (max_side / total) * 100
        return skew_pct > self.MAX_INVENTORY_SKEW_PCT

    # ------------------------------------------------------------------
    # COMPREHENSIVE TRADE RESULT RECORDING
    # ------------------------------------------------------------------

    def record_trade_result(self, buy_ex: str, sell_ex: str, symbol: str,
                            net_profit_pct: float, slippage_pct: float,
                            latency_ms: float, filled: bool = True):
        """Record comprehensive trade result for all Stage 4-7 systems."""
        # Stage 4: Pair scoring
        self.record_pair_result(buy_ex, sell_ex, net_profit_pct, slippage_pct, latency_ms)

        # Stage 4: Slippage history
        self.record_slippage(slippage_pct)

        # Stage 3: Fill stats
        self.record_fill(buy_ex, filled)
        self.record_fill(sell_ex, filled)

        # Stage 7: Kill-switch checks
        self.check_slippage_kill(buy_ex, slippage_pct)
        self.check_slippage_kill(sell_ex, slippage_pct)
        self.check_fill_rate_kill(buy_ex)
        self.check_fill_rate_kill(sell_ex)

    # ------------------------------------------------------------------
    # SUMMARY / STATUS
    # ------------------------------------------------------------------

    def get_summary(self) -> str:
        """Return human-readable status summary."""
        latencies = ", ".join(
            f"{ex}={s.ema_ms:.0f}ms"
            for ex, s in sorted(self._latency.items(), key=lambda x: x[1].ema_ms)
        ) or "no data"

        fills = ", ".join(
            f"{ex}={s.fill_rate:.0%}"
            for ex, s in self._fill_stats.items() if s.attempts > 0
        ) or "no data"

        top_pairs = self.get_top_pairs(3)
        pairs_str = ", ".join(top_pairs) or "no data"

        vol = self._vol_regime.regime

        return (
            f"Latency: [{latencies}] | "
            f"Fills: [{fills}] | "
            f"TopPairs: [{pairs_str}] | "
            f"VolRegime: {vol}"
        )
