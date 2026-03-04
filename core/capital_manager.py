"""
CapitalManager — Adaptive capital-level mode selection for Arbitrage Engine 2.0.

Manages 4 trading modes based on equity:
  Level 1: MicroArbMode   ($14–150)  — Single-coin cross-exchange arb
  Level 2: MultiCoinMode  ($150–300) — Multi-coin parallel arb
  Level 3: StatArbMode    ($300–1000)— Statistical arbitrage (pairs/cointegration)
  Level 4: MarketMakingMode ($1000+) — Market making + hedging

Each level has its own parameter set optimised for capital efficiency.
"""

import time
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# CAPITAL LEVEL DEFINITIONS
# ============================================================================

@dataclass(frozen=True)
class LevelParams:
    """Immutable parameter set for a capital level."""
    name: str
    min_equity: float            # Total equity across ALL exchanges
    spread_persistence_ms: int   # Spread must hold this long before trading
    spread_threshold_above_fees: float  # Spread must exceed fees by this pct
    max_slippage_pct: float      # Max allowed slippage per leg
    min_net_profit_pct: float    # Min net profit % after all costs
    min_net_profit_usdt: float   # Min absolute profit per trade (USD)
    max_exposure_per_exchange_pct: float  # % of total capital on one exchange
    max_exposure_per_coin_pct: float      # % of total capital in one coin
    max_parallel_trades: int     # Max concurrent open trades
    coin_limit: int              # Max number of coins to trade simultaneously
    working_capital_pct: float   # % of capital used for trading (rest = reserve)
    position_size_pct: float     # % of exchange balance per position
    htx_min_spread_pct: float    # HTX only used above this spread (higher latency)


LEVEL_1_MICRO = LevelParams(
    name="MicroArb",
    min_equity=0,          # Default for any capital
    spread_persistence_ms=150,
    spread_threshold_above_fees=0.015,  # Pre-positioned arb: only sell-side slippage (~0.01-0.02%)
    max_slippage_pct=0.15,
    min_net_profit_pct=0.01,   # Micro-profits: $5 × 0.01% = $0.0005 (volume-based)
    min_net_profit_usdt=0.001, # $0.001 minimum (many small trades add up)
    max_exposure_per_exchange_pct=35.0,
    max_exposure_per_coin_pct=25.0,
    max_parallel_trades=1,
    coin_limit=1,
    working_capital_pct=85.0,
    position_size_pct=35.0,
    htx_min_spread_pct=0.30,   # HTX allowed above 0.30% (pre-positioned)
)

LEVEL_2_MULTI = LevelParams(
    name="MultiCoin",
    min_equity=150,
    spread_persistence_ms=120,
    spread_threshold_above_fees=0.012,  # Pre-positioned: tighter cushion with more capital
    max_slippage_pct=0.15,
    min_net_profit_pct=0.01,   # Micro-profits at scale
    min_net_profit_usdt=0.002,
    max_exposure_per_exchange_pct=35.0,
    max_exposure_per_coin_pct=20.0,
    max_parallel_trades=3,
    coin_limit=3,
    working_capital_pct=85.0,
    position_size_pct=35.0,
    htx_min_spread_pct=0.25,
)

LEVEL_3_STAT = LevelParams(
    name="StatArb",
    min_equity=300,
    spread_persistence_ms=100,
    spread_threshold_above_fees=0.010,  # Tighter with higher volume
    max_slippage_pct=0.15,
    min_net_profit_pct=0.01,
    min_net_profit_usdt=0.005,
    max_exposure_per_exchange_pct=30.0,
    max_exposure_per_coin_pct=15.0,
    max_parallel_trades=5,
    coin_limit=5,
    working_capital_pct=85.0,
    position_size_pct=30.0,
    htx_min_spread_pct=0.20,
)

LEVEL_4_MM = LevelParams(
    name="MarketMaking",
    min_equity=1000,
    spread_persistence_ms=80,
    spread_threshold_above_fees=0.008,  # Tightest with high capital
    max_slippage_pct=0.12,
    min_net_profit_pct=0.01,
    min_net_profit_usdt=0.01,
    max_exposure_per_exchange_pct=30.0,
    max_exposure_per_coin_pct=15.0,
    max_parallel_trades=8,
    coin_limit=6,
    working_capital_pct=85.0,
    position_size_pct=25.0,
    htx_min_spread_pct=0.30,
)

ALL_LEVELS = [LEVEL_4_MM, LEVEL_3_STAT, LEVEL_2_MULTI, LEVEL_1_MICRO]


# ============================================================================
# KILL-LOGIC: Coin and Exchange Disabling
# ============================================================================

@dataclass
class _CoinHealth:
    """Tracks consecutive losses for a coin."""
    consecutive_losses: int = 0
    disabled_until: float = 0.0


@dataclass
class _ExchangeHealth:
    """Tracks slippage quality for an exchange."""
    slippage_samples: list = field(default_factory=list)
    trade_results: list = field(default_factory=list)    # (timestamp, profit_pct)
    disabled_until: float = 0.0
    total_trades: int = 0


# ============================================================================
# CAPITAL MANAGER
# ============================================================================

class CapitalManager:
    """
    Central capital + risk coordinator.

    Responsibilities:
      1. Determine current capital level → select LevelParams
      2. Track coin / exchange health → kill-logic
      3. Compute dynamic spread threshold
      4. Adaptive position sizing (compound scaling)
      5. Exchange quality ranking
      6. Overtrading control
    """

    # Kill-logic constants
    COIN_MAX_CONSECUTIVE_LOSSES = 3
    COIN_DISABLE_SECONDS = 7200      # 2 hours
    EXCHANGE_SLIPPAGE_WINDOW = 100    # last N samples
    EXCHANGE_MAX_AVG_SLIPPAGE = 0.35  # 0.35%
    EXCHANGE_DISABLE_SECONDS = 3600   # 1 hour
    EXCHANGE_RANK_EVERY_N = 100       # re-rank every N trades

    # Latency-to-risk conversion: 330ms → 0.001% price risk
    # Pre-positioned arb has lower latency risk since buy is maker (limit)
    LATENCY_RISK_FACTOR = 0.000003

    # Adaptive scaling
    COMPOUND_EQUITY_STEP_PCT = 10.0   # Every +10% equity → scale up
    COMPOUND_SCALE_FACTOR = 1.05      # +5% per step
    MAX_COMPOUND_MULTIPLIER = 2.0     # Cap at 2× base position size

    # Overtrading control
    OVERTRADING_WINDOW = 10           # Last N trades to check
    OVERTRADING_MIN_AVG_PROFIT = 0.20 # 0.20%
    OVERTRADING_THRESHOLD_BUMP = 0.05 # +0.05% when overtrading detected
    OVERTRADING_BUMP_DECAY_SEC = 300.0  # Bump decays after 5 minutes

    # Volatility regime
    HIGH_VOLATILITY_THRESHOLD = 3.0   # % — reduce size (crypto often moves >1.5%/day normally)
    HIGH_VOLATILITY_SIZE_REDUCTION = 0.20  # -20%
    HIGH_VOLATILITY_THRESHOLD_BUMP = 0.05  # +0.05%

    def __init__(self, initial_equity: float = 70.0):
        self._initial_equity = initial_equity
        self._current_equity = initial_equity
        self._current_level: LevelParams = LEVEL_1_MICRO

        # Kill-logic state
        self._coin_health: Dict[str, _CoinHealth] = {}
        self._exchange_health: Dict[str, _ExchangeHealth] = {}

        # Trade history for overtrading detection
        self._recent_profits: List[float] = []  # last N net profit pct
        self._total_trades_completed = 0  # Track total trades for compound gating

        # Exchange quality ranking
        self._exchange_scores: Dict[str, float] = {}

        # Overtrading bump (added to dynamic threshold when overtrading detected)
        self._overtrading_bump = 0.0
        self._overtrading_bump_set_time = 0.0  # When bump was last set

        # Volatility regime
        self._current_volatility_pct = 0.0

        self._select_level()
        logger.info(f"💰 CapitalManager initialized: ${initial_equity:.2f} → {self._current_level.name}")

    # ------------------------------------------------------------------
    # LEVEL SELECTION
    # ------------------------------------------------------------------

    def _select_level(self):
        for lvl in ALL_LEVELS:
            if self._current_equity >= lvl.min_equity:
                if self._current_level.name != lvl.name:
                    logger.info(
                        f"📊 Capital level change: {self._current_level.name} → {lvl.name} "
                        f"(equity=${self._current_equity:.2f})"
                    )
                self._current_level = lvl
                return

    def update_equity(self, equity: float):
        """Call periodically with total equity across all exchanges."""
        self._current_equity = equity
        self._select_level()

    @property
    def level(self) -> LevelParams:
        return self._current_level

    @property
    def equity(self) -> float:
        return self._current_equity

    # ------------------------------------------------------------------
    # DYNAMIC THRESHOLD  (Section 2.0 PHASE 5)
    # ------------------------------------------------------------------

    def dynamic_threshold(self, total_fee_pct: float,
                          avg_latency_ms: float = 0.0) -> float:
        """Compute the dynamic minimum spread required for a profitable trade.

        TOP BOT PATTERN (CCXT/Hummingbot/Barbotine):
        threshold = total_fees + small_buffer (0.01-0.02%)
        
        Simplified from 5-7 factors to just: fees + level cushion.
        Latency/volatility/overtrading factors REMOVED — they were blocking
        profitable trades that top bots would execute successfully.
        """
        lvl = self._current_level
        threshold = total_fee_pct + lvl.spread_threshold_above_fees
        return threshold

    def update_volatility(self, volatility_pct: float):
        """Update current market volatility (e.g. 10-period ATR %)."""
        self._current_volatility_pct = max(0.0, volatility_pct)

    # ------------------------------------------------------------------
    # POSITION SIZING (Section 2.0 PHASE 3)
    # ------------------------------------------------------------------

    def compute_position_usdt(self, exchange_balance_usdt: float,
                              depth_best_usdt: float,
                              exposure_limit_usdt: float) -> float:
        """Compute position size in USDT.

        size = min(
            position_size_pct% × exchange_balance,
            70% × depth_best,
            exposure_limit
        ) × compound_multiplier × volatility_adjustment

        Working capital = 85% of exchange balance.
        """
        lvl = self._current_level
        working = exchange_balance_usdt * (lvl.working_capital_pct / 100.0)
        base = min(
            working * (lvl.position_size_pct / 100.0),
            depth_best_usdt * 0.70,
            exposure_limit_usdt,
        )
        base *= self._compound_multiplier()
        base *= self._volatility_size_adjustment()
        return max(0.0, base)

    def _compound_multiplier(self) -> float:
        """Adaptive position scaling: +5% per 10% equity growth.
        
        Returns 1.0 until at least 1 trade is completed to avoid
        false inflation from pre-fund operations (buying coins reduces
        USDT but doesn't change total equity).
        """
        if self._total_trades_completed < 1:
            return 1.0
        if self._initial_equity <= 0:
            return 1.0
        growth_pct = ((self._current_equity / self._initial_equity) - 1.0) * 100.0
        if growth_pct <= 0:
            return 1.0
        steps = growth_pct / self.COMPOUND_EQUITY_STEP_PCT
        return min(self.COMPOUND_SCALE_FACTOR ** steps, self.MAX_COMPOUND_MULTIPLIER)

    def _volatility_size_adjustment(self) -> float:
        """Reduce position size in high-volatility regime."""
        if self._current_volatility_pct > self.HIGH_VOLATILITY_THRESHOLD:
            return 1.0 - self.HIGH_VOLATILITY_SIZE_REDUCTION
        return 1.0

    # ------------------------------------------------------------------
    # KILL-LOGIC: COIN (Section 2.0 PHASE 6)
    # ------------------------------------------------------------------

    def record_trade_result(self, symbol: str, buy_exchange: str,
                            sell_exchange: str, net_profit_pct: float,
                            slippage_pct: float = 0.0):
        """Record a completed trade for kill-logic + quality tracking."""
        now = time.time()
        self._total_trades_completed += 1

        # --- coin health ---
        ch = self._coin_health.setdefault(symbol, _CoinHealth())
        if net_profit_pct < 0:
            ch.consecutive_losses += 1
            if ch.consecutive_losses >= self.COIN_MAX_CONSECUTIVE_LOSSES:
                ch.disabled_until = now + self.COIN_DISABLE_SECONDS
                logger.warning(
                    f"🚫 KILL: {symbol} disabled for {self.COIN_DISABLE_SECONDS // 60}min "
                    f"after {ch.consecutive_losses} consecutive losses"
                )
        else:
            ch.consecutive_losses = 0

        # --- exchange health ---
        for ex in (buy_exchange, sell_exchange):
            eh = self._exchange_health.setdefault(ex, _ExchangeHealth())
            eh.total_trades += 1
            if slippage_pct > 0:
                eh.slippage_samples.append(slippage_pct)
                if len(eh.slippage_samples) > self.EXCHANGE_SLIPPAGE_WINDOW:
                    eh.slippage_samples = eh.slippage_samples[-self.EXCHANGE_SLIPPAGE_WINDOW:]
            eh.trade_results.append((now, net_profit_pct))
            if len(eh.trade_results) > 200:
                eh.trade_results = eh.trade_results[-200:]

            # Check if exchange should be disabled
            if len(eh.slippage_samples) >= 10:
                avg_slip = sum(eh.slippage_samples) / len(eh.slippage_samples)
                if avg_slip > self.EXCHANGE_MAX_AVG_SLIPPAGE:
                    eh.disabled_until = now + self.EXCHANGE_DISABLE_SECONDS
                    logger.warning(
                        f"🚫 KILL: {ex} disabled for {self.EXCHANGE_DISABLE_SECONDS // 60}min "
                        f"(avg slippage {avg_slip:.3f}% > {self.EXCHANGE_MAX_AVG_SLIPPAGE}%)"
                    )

        # --- overtrading detection ---
        self._recent_profits.append(net_profit_pct)
        if len(self._recent_profits) > self.OVERTRADING_WINDOW:
            self._recent_profits = self._recent_profits[-self.OVERTRADING_WINDOW:]
        if len(self._recent_profits) >= self.OVERTRADING_WINDOW:
            avg = sum(self._recent_profits) / len(self._recent_profits)
            if avg < self.OVERTRADING_MIN_AVG_PROFIT:
                self._overtrading_bump = self.OVERTRADING_THRESHOLD_BUMP
                self._overtrading_bump_set_time = time.time()
            else:
                self._overtrading_bump = 0.0
                self._overtrading_bump_set_time = 0.0

        # --- periodic exchange ranking ---
        total = sum(eh.total_trades for eh in self._exchange_health.values())
        if total > 0 and total % self.EXCHANGE_RANK_EVERY_N == 0:
            self._rank_exchanges()

    def is_coin_enabled(self, symbol: str) -> bool:
        """Check if a coin is not in kill-disable period."""
        ch = self._coin_health.get(symbol)
        if ch is None:
            return True
        if ch.disabled_until > time.time():
            return False
        return True

    def is_exchange_enabled(self, exchange: str) -> bool:
        """Check if an exchange is not in kill-disable period."""
        eh = self._exchange_health.get(exchange)
        if eh is None:
            return True
        if eh.disabled_until > time.time():
            return False
        return True

    # ------------------------------------------------------------------
    # EXCHANGE QUALITY RANKING (Section 5 — item 3)
    # ------------------------------------------------------------------

    def _rank_exchanges(self):
        """Re-rank exchanges by quality every EXCHANGE_RANK_EVERY_N trades.

        score = winrate × avg_profit / max(avg_slippage, 0.01)
        """
        now = time.time()
        for ex, eh in self._exchange_health.items():
            recent = [(t, p) for t, p in eh.trade_results if now - t < 86400]
            if len(recent) < 5:
                self._exchange_scores[ex] = 1.0
                continue
            wins = sum(1 for _, p in recent if p > 0)
            winrate = wins / len(recent) if recent else 0.5
            avg_profit = sum(p for _, p in recent) / len(recent) if recent else 0.0
            avg_slip = (
                sum(eh.slippage_samples[-50:]) / len(eh.slippage_samples[-50:])
                if eh.slippage_samples else 0.01
            )
            score = winrate * max(avg_profit, 0.001) / max(avg_slip, 0.01)
            self._exchange_scores[ex] = round(score, 4)

        if self._exchange_scores:
            ranked = sorted(self._exchange_scores.items(), key=lambda x: -x[1])
            logger.info(f"📊 Exchange ranking: {', '.join(f'{e}={s:.3f}' for e, s in ranked)}")

    def get_exchange_score(self, exchange: str) -> float:
        return self._exchange_scores.get(exchange, 1.0)

    # ------------------------------------------------------------------
    # CONVENIENCE GETTERS
    # ------------------------------------------------------------------

    def should_use_htx(self, spread_pct: float) -> bool:
        """HTX has higher latency — only use if spread is wide enough."""
        return spread_pct >= self._current_level.htx_min_spread_pct

    @property
    def level(self):
        """Public access to current trading level."""
        return self._current_level

    @property
    def compound_multiplier(self) -> float:
        """Public access to compound multiplier."""
        return self._compound_multiplier()

    def get_summary(self) -> str:
        """Return human-readable status summary."""
        lvl = self._current_level
        disabled_coins = [
            s for s, ch in self._coin_health.items()
            if ch.disabled_until > time.time()
        ]
        disabled_exs = [
            e for e, eh in self._exchange_health.items()
            if eh.disabled_until > time.time()
        ]
        return (
            f"Level={lvl.name} | Equity=${self._current_equity:.2f} | "
            f"Coins:{lvl.coin_limit} | "
            f"Parallel:{lvl.max_parallel_trades} | "
            f"Pos%:{lvl.position_size_pct} | "
            f"Compound:{self._compound_multiplier():.2f}× | "
            f"Disabled coins:{disabled_coins or 'none'} | "
            f"Disabled exs:{disabled_exs or 'none'}"
        )
