#!/usr/bin/env python3
"""
Configuration settings for the arbitrage bot.
All settings have safe, conservative defaults suitable for initial testing.
Override via environment variables with ARB_ prefix or by modifying defaults below.

ENHANCED VERSION - Added 30+ new parameters for autonomous trading
"""
import os
from typing import Optional, List


def _get_env_bool(key: str, default: bool) -> bool:
    """Get boolean from environment variable."""
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes", "on")


def _get_env_float(key: str, default: float) -> float:
    """Get float from environment variable."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _get_env_int(key: str, default: int) -> int:
    """Get int from environment variable."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _get_env_str(key: str, default: str) -> str:
    """Get string from environment variable."""
    return os.getenv(key, default)


# ============================================================================
# ORDER EXECUTION MODE
# ============================================================================
# CRITICAL: Set to True only when ready for real trading with funded accounts
# Default is False for safety - all orders will be simulated
DRY_RUN = _get_env_bool("ARB_DRY_RUN", True)

# Virtual capital per exchange for dry-run mode (USDT)
# In dry-run, the bot uses this virtual balance instead of querying real exchanges
VIRTUAL_CAPITAL_PER_EXCHANGE = _get_env_float("ARB_VIRTUAL_CAPITAL", 20.0)

# ============================================================================
# EXCHANGE API CREDENTIALS
# ============================================================================
# Bybit
BYBIT_API_KEY = _get_env_str("ARB_BYBIT_KEY", "")
BYBIT_API_SECRET = _get_env_str("ARB_BYBIT_SECRET", "")

# KuCoin
KUCOIN_API_KEY = _get_env_str("ARB_KUCOIN_KEY", "")
KUCOIN_API_SECRET = _get_env_str("ARB_KUCOIN_SECRET", "")
KUCOIN_PASSPHRASE = _get_env_str("ARB_KUCOIN_PASSPHRASE", "")

# HTX (Huobi)
HTX_API_KEY = _get_env_str("ARB_HTX_KEY", "")
HTX_API_SECRET = _get_env_str("ARB_HTX_SECRET", "")

# MEXC
MEXC_API_KEY = _get_env_str("ARB_MEXC_KEY", "")
MEXC_API_SECRET = _get_env_str("ARB_MEXC_SECRET", "")

# XT
XT_API_KEY = _get_env_str("ARB_XT_KEY", "")
XT_API_SECRET = _get_env_str("ARB_XT_SECRET", "")

# Binance
BINANCE_API_KEY = _get_env_str("ARB_BINANCE_KEY", "")
BINANCE_API_SECRET = _get_env_str("ARB_BINANCE_SECRET", "")

# Telegram Bot (Optional)
TELEGRAM_BOT_TOKEN = _get_env_str("ARB_TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = _get_env_str("ARB_TELEGRAM_CHAT_ID", "")

# ============================================================================
# RISK MANAGEMENT PARAMETERS
# ============================================================================
# Minimum net ROI percentage required to execute trade (after fees & slippage)
# Minimum percentage ROI after fees to consider executing (0.03 = 0.03%)
# Phase 9: minimum allowed profit = 0.03% to avoid marginal trades
MIN_NET_ROI_PCT = _get_env_float("ARB_MIN_NET_ROI_PCT", 0.03)

# Maximum exposure per trade in USDT
# Auto-scales to 60% of per-exchange capital (works for any balance size)
# Override with ARB_MAX_EXPOSURE_USDT env var for custom value
_default_exposure = VIRTUAL_CAPITAL_PER_EXCHANGE * 0.6
MAX_EXPOSURE_USDT = _get_env_float("ARB_MAX_EXPOSURE_USDT", _default_exposure)

# Safety factor for liquidity (use only this fraction of available liquidity)
# 0.5 = use max 50% of available liquidity to avoid slippage
SAFETY_FACTOR = _get_env_float("ARB_SAFETY_FACTOR", 0.5)

# Maximum number of trades per minute (rate limiting)
# TOP BOT PATTERN: Allow high-frequency trading — top bots execute every opportunity
MAX_TRADES_PER_MINUTE = _get_env_int("ARB_MAX_TRADES_PER_MINUTE", 30)

# Cooldown period in seconds before same symbol can be traded again
# TOP BOT PATTERN: CCXT/Hummingbot allow rapid re-entry on same symbols
# 1.0s prevents double-execution of same spread but allows fast trading
PER_SYMBOL_COOLDOWN_SEC = _get_env_float("ARB_SYMBOL_COOLDOWN_SEC", 1.0)
SYMBOL_COOLDOWN_SEC = PER_SYMBOL_COOLDOWN_SEC  # Alias for compatibility

# Maximum concurrent opportunities to process per scan cycle
MAX_CONCURRENT_OPPORTUNITIES = _get_env_int("ARB_MAX_CONCURRENT_OPPS", 3)

# ============================================================================
# MULTI-LAYER RISK LIMITS (Strategy A5)
# Auto-scale risk limits based on total capital (virtual or live)
# ============================================================================
NUM_EXCHANGES = 5
DAILY_LOSS_PCT = 0.05        # Max daily loss = 5% of total capital (Phase 14)
SINGLE_TRADE_LOSS_PCT = 0.01 # Max loss per trade = 1% of total capital (Phase 14)
HOURLY_LOSS_PCT = 0.02       # Max hourly loss = 2% of total capital (sub-fraction of daily)
OPEN_EXPOSURE_PCT = 0.60     # Max open exposure = 60% of total capital

_total_capital = VIRTUAL_CAPITAL_PER_EXCHANGE * NUM_EXCHANGES
MAX_DAILY_LOSS = _get_env_float("ARB_MAX_DAILY_LOSS", _total_capital * DAILY_LOSS_PCT)
MAX_SINGLE_TRADE_LOSS = _get_env_float("ARB_MAX_SINGLE_TRADE_LOSS", _total_capital * SINGLE_TRADE_LOSS_PCT)
MAX_HOURLY_LOSS = _get_env_float("ARB_MAX_HOURLY_LOSS", _total_capital * HOURLY_LOSS_PCT)
MAX_OPEN_EXPOSURE = _get_env_float("ARB_MAX_OPEN_EXPOSURE", _total_capital * OPEN_EXPOSURE_PCT)
MAX_CONSECUTIVE_LOSSES = _get_env_int("ARB_MAX_CONSECUTIVE_LOSSES", 5)  # Pause after N losses
ANOMALOUS_SPREAD_PCT = _get_env_float("ARB_ANOMALOUS_SPREAD_PCT", 5.0)  # Skip spreads above this
MAX_DATA_AGE_SEC = _get_env_float("ARB_MAX_DATA_AGE_SEC", 2.0)  # Aligned with MAX_ORDERBOOK_AGE_MS (2s). 0.5s was too aggressive for home PCs.
MIN_LIVE_ROI_PCT = _get_env_float("ARB_MIN_LIVE_ROI_PCT", 0.03)  # Min ROI% to execute live (Phase 9: floor at 0.03%)
MIN_BALANCE_PER_EXCHANGE = _get_env_float("ARB_MIN_BALANCE_PER_EXCHANGE", 8.0)  # Min balance to trade (lowered for small accounts)
MIN_TRADE_SIZE_USDT = _get_env_float("ARB_MIN_TRADE_SIZE_USDT", 8.0)  # Target trade size 8-12 USDT (Phase 8)
BALANCE_RESERVE_USDT = _get_env_float("ARB_BALANCE_RESERVE_USDT", 2.0)  # Keep reserve on each exchange
MAX_BALANCE_USAGE_PCT = _get_env_float("ARB_MAX_BALANCE_USAGE_PCT", 75.0)  # AGGRESSIVE: 75% for max capital utilization

# ============================================================================
# CAPITAL-AWARE STRATEGY PRIORITY
# ============================================================================
# Strategies ranked by profitability at different capital levels.
# Each strategy has: min_capital (per exchange), priority (1=highest),
# and expected_edge (historical average profit per trade %).
# Strategies below min_capital are DISABLED to avoid fee-losing trades.
STRATEGY_PRIORITY = {
    # Tier 1: Works with ANY capital ($5+) — pure cross-exchange spread
    'CROSS_EXCHANGE':  {'min_capital': 5,    'priority': 1, 'edge_pct': 0.05},
    'SMART_ORDER':     {'min_capital': 5,    'priority': 2, 'edge_pct': 0.04},
    'MAKER_MAKER':     {'min_capital': 5,    'priority': 3, 'edge_pct': 0.06},
    # Tier 2: Works with small capital ($10+) — statistical signals
    'FUNDING_RATE':    {'min_capital': 10,   'priority': 4, 'edge_pct': 0.08},
    'INDEX_ARB':       {'min_capital': 10,   'priority': 5, 'edge_pct': 0.06},
    'VOLATILITY_ARB':  {'min_capital': 10,   'priority': 6, 'edge_pct': 0.05},
    'VOLATILITY':      {'min_capital': 10,   'priority': 7, 'edge_pct': 0.03},
    # Tier 3: Medium capital ($25+) — needs multiple positions
    'PAIRS_TRADING':   {'min_capital': 25,   'priority': 8, 'edge_pct': 0.10},
    'SPREAD_BETTING':  {'min_capital': 25,   'priority': 9, 'edge_pct': 0.08},
    'MARKET_MAKING':   {'min_capital': 25,   'priority': 10, 'edge_pct': 0.06},
    'MOMENTUM':        {'min_capital': 25,   'priority': 11, 'edge_pct': 0.12},
    # Tier 4: Larger capital ($50+) — long-term hold strategies
    'DCA':             {'min_capital': 50,   'priority': 12, 'edge_pct': 0.15},
    'GRID_TRADING':    {'min_capital': 50,   'priority': 13, 'edge_pct': 0.10},
    'BREAKOUT':        {'min_capital': 50,   'priority': 14, 'edge_pct': 0.20},
    'TRIANGULAR':      {'min_capital': 100,  'priority': 15, 'edge_pct': 0.15},
}

# ============================================================================
# STRATEGY CLASSIFICATION — separates arb from directional strategies
# ============================================================================
# Market-neutral strategies: can execute in arb mode (hedge both sides)
ARB_STRATEGIES = frozenset({'CROSS_EXCHANGE', 'TRIANGULAR', 'SMART_ORDER', 'FUNDING_RATE', 
                            'INDEX_ARB', 'VOLATILITY_ARB', 'SPREAD_BETTING', 'PAIRS_TRADING',
                            'MAKER_MAKER'})

# Directional strategies: SIGNAL ONLY, NEVER execute trades.
# These are DISABLED from scanning to save CPU for the arb strategies that
# actually generate profit. They cannot execute because:
#   1. They fail _is_executable() (no cross-exchange premium)
#   2. They hit DIRECTIONAL_STRATEGIES block in _build_trade_from_signal()
# CPU savings: ~30% less scanning overhead → faster arb detection
DIRECTIONAL_STRATEGIES = frozenset({'VOLATILITY', 'MOMENTUM', 'BREAKOUT', 'DCA', 
                                    'GRID_TRADING'})

# DISABLED_STRATEGIES: strategies excluded from scanning entirely.
# MARKET_MAKING is enabled for Level 4+ ($1000+) via capital_manager.
# MAKER_MAKER is always enabled (uses limit orders on both sides).
DISABLED_STRATEGIES = frozenset(DIRECTIONAL_STRATEGIES)

# ============================================================================
# EXPOSURE CAPS — per-coin and per-exchange limits
# ============================================================================
# Maximum percentage of total capital in any single coin
MAX_EXPOSURE_PER_COIN_PCT = _get_env_float("ARB_MAX_EXPOSURE_PER_COIN_PCT", 15.0)

# Maximum percentage of total capital on any single exchange  
MAX_EXPOSURE_PER_EXCHANGE_PCT = _get_env_float("ARB_MAX_EXPOSURE_PER_EXCHANGE_PCT", 30.0)

# Maximum percentage of total capital per single trade (position size limit)
MAX_EXPOSURE_PER_TRADE_PCT = _get_env_float("ARB_MAX_EXPOSURE_PER_TRADE_PCT", 5.0)

# Maximum inventory imbalance per coin across exchanges (USDT equivalent)
# If imbalance exceeds this, stop trading that direction
MAX_INVENTORY_SKEW_USDT = _get_env_float("ARB_MAX_INVENTORY_SKEW_USDT", 20.0)

# ============================================================================
# CAPITAL DISTRIBUTION — target allocation per exchange (Phase 26)
# ============================================================================
# MEXC gets highest share (0% maker fees = more profitable arb legs)
# Bybit/Binance share equally (liquid, fast, low fees)
# KuCoin/HTX get less (higher fees/latency)
EXCHANGE_TARGET_PCT = {
    'MEXC': 30,
    'Bybit': 25,
    'Binance': 25,
    'KuCoin': 10,
    'HTX': 10,
}

# ============================================================================
# MINIMUM 24H VOLUME FILTER — reject illiquid pairs (Phase 31)
# ============================================================================
MIN_24H_VOLUME_USDT = _get_env_float("ARB_MIN_24H_VOLUME_USDT", 10_000_000)  # 10M USDT

# Pairs known to frequently have <10M 24h volume on smaller exchanges.
# Updated periodically. The 20 core pairs (BTC, ETH, SOL, etc.) are always liquid.
# These low-cap/low-volume tokens may lack sufficient depth for safe arb execution.
LOW_VOLUME_SYMBOLS = frozenset({
    "FLOW-USDT", "CHZ-USDT", "SAND-USDT", "AXS-USDT",
    "BLUR-USDT", "SNX-USDT", "CRV-USDT",
})

# ============================================================================
# GLOBAL SLIPPAGE BUFFER
# ============================================================================
# Applied to ALL strategy ROI calculations before trade execution.
# With maker-first execution: buy side (limit) has ~0 slippage.
# Only sell side (market) carries slippage risk: ~0.03% per leg.
# 0.03% per leg × 2 legs = 0.06% total (but buy-side is ~0 for maker).
GLOBAL_SLIPPAGE_PER_LEG_PCT = _get_env_float("ARB_SLIPPAGE_PER_LEG_PCT", 0.01)

# ============================================================================
# ENGINE 2.0 — MAKER-FIRST EXECUTION MODEL
# ============================================================================
# Instead of market+market (double taker fee), use limit_buy + market_sell:
#   1. Place limit buy at best_bid + 20% of spread
#   2. Wait up to MAKER_FILL_TIMEOUT_MS for ≥ MAKER_MIN_FILL_PCT fill
#   3. If filled → instant market sell
#   4. If spread disappears or timeout → cancel
# SMART EXECUTION: maker-first for MEXC buys (0% maker fee → saves 0.05%),
# simultaneous market orders for all other exchange pairs.
# This follows Hummingbot XEMM pattern: use limit order on favorable-fee side.
# Scan slippage calculation (arbitrage.py:749) uses this flag too.
MAKER_FIRST_ENABLED = _get_env_bool("ARB_MAKER_FIRST", True)
MAKER_FILL_TIMEOUT_MS = _get_env_int("ARB_MAKER_FILL_TIMEOUT_MS", 250)
MAKER_MIN_FILL_PCT = _get_env_float("ARB_MAKER_MIN_FILL_PCT", 75.0)
MAKER_PRICE_OFFSET_PCT = _get_env_float("ARB_MAKER_PRICE_OFFSET_PCT", 20.0)  # % of spread

# ============================================================================
# ENGINE 2.0 — WORKING CAPITAL / RESERVE SPLIT
# ============================================================================
# 85% of capital is actively traded; 15% is kept as reserve (buffer for
# drawdowns, funding withdrawals, or emergency hedging).
WORKING_CAPITAL_PCT = _get_env_float("ARB_WORKING_CAPITAL_PCT", 85.0)

# ============================================================================
# ENGINE 2.0 — ORDERBOOK STALENESS PROTECTION
# ============================================================================
# 2000ms (2s) is realistic for home PC with 200-400ms network latency.
# WS updates arrive every 100-500ms; processing adds 50-200ms.
# 200ms was rejecting virtually ALL data — no trades could execute.
MAX_ORDERBOOK_AGE_MS = _get_env_int("ARB_MAX_ORDERBOOK_AGE_MS", 2000)

# ============================================================================
# ENGINE 2.0 — DEPTH IMPACT PROTECTION
# ============================================================================
# min_depth_at_best >= DEPTH_MULTIPLE × planned_position
DEPTH_MULTIPLE = _get_env_float("ARB_DEPTH_MULTIPLE", 4.0)

# ============================================================================
# ENGINE 2.0 — SLIPPAGE & PROFIT PROTECTION
# ============================================================================
# Maximum acceptable slippage per order leg (cancel if exceeds)
MAX_SLIPPAGE_PCT = _get_env_float("ARB_MAX_SLIPPAGE_PCT", 0.2)
# Minimum expected net profit in USDT to execute a trade
# At $72 capital: position ~$5, 0.08% edge = $0.004.
# Must be below smallest expected profit to avoid blocking all trades.
MIN_LIVE_NET_PROFIT = _get_env_float("ARB_MIN_LIVE_NET_PROFIT", 0.001)
# Maximum VWAP vs top-of-book slippage (deeper book → reject)
MAX_VWAP_SLIPPAGE_PCT = _get_env_float("ARB_MAX_VWAP_SLIPPAGE_PCT", 0.3)
# Reserve percentage (complement of WORKING_CAPITAL_PCT)
RESERVE_PCT = 100.0 - WORKING_CAPITAL_PCT

# ============================================================================
# SEMI-HFT ENGINE — Professional execution layer
# ============================================================================
# Enable semi-HFT features (per-symbol locks, event-driven, predictive maker)
SEMI_HFT_ENABLED = _get_env_bool("ARB_SEMI_HFT", True)

# Stage 1: Maximum exchange RTT before exclusion (ms)
SEMI_HFT_MAX_RTT_MS = _get_env_float("ARB_HFT_MAX_RTT_MS", 450.0)

# Stage 2: Spread change trigger for event-driven rescan (%)
SEMI_HFT_SPREAD_TRIGGER_PCT = _get_env_float("ARB_HFT_SPREAD_TRIGGER", 0.02)

# Stage 3: Minimum fill probability to use maker model (0-1)
SEMI_HFT_MIN_FILL_PROB = _get_env_float("ARB_HFT_MIN_FILL_PROB", 0.50)
# Start proportional hedge at this fill % (default: 30% instead of 75%)
SEMI_HFT_EARLY_HEDGE_PCT = _get_env_float("ARB_HFT_EARLY_HEDGE_PCT", 30.0)
# Split orders into N micro-slices
SEMI_HFT_ORDER_SLICES = _get_env_int("ARB_HFT_ORDER_SLICES", 3)

# Stage 7: Kill-switch thresholds
SEMI_HFT_LATENCY_KILL_MS = _get_env_float("ARB_HFT_LATENCY_KILL_MS", 500.0)
SEMI_HFT_SLIPPAGE_KILL_PCT = _get_env_float("ARB_HFT_SLIPPAGE_KILL_PCT", 0.5)
SEMI_HFT_MIN_FILL_RATE_PCT = _get_env_float("ARB_HFT_MIN_FILL_RATE_PCT", 40.0)
SEMI_HFT_MAX_INVENTORY_SKEW_PCT = _get_env_float("ARB_HFT_MAX_INVENTORY_SKEW_PCT", 60.0)
# Lead-lag ROI boost when timing is favorable (buy on lagger, sell on leader)
SEMI_HFT_LEAD_LAG_BOOST_PCT = _get_env_float("ARB_HFT_LEAD_LAG_BOOST_PCT", 0.02)

def get_enabled_strategies(capital_per_exchange: float = None) -> list:
    """Return list of strategy names enabled for current capital level.
    
    Strategies with min_capital > user's per-exchange balance are DISABLED
    because they can't generate enough profit to cover fees at that size.
    """
    if capital_per_exchange is None:
        capital_per_exchange = VIRTUAL_CAPITAL_PER_EXCHANGE
    enabled = []
    for name, cfg in sorted(STRATEGY_PRIORITY.items(), key=lambda x: x[1]['priority']):
        if capital_per_exchange >= cfg['min_capital']:
            enabled.append(name)
    return enabled

# ============================================================================
# PERFORMANCE & THROTTLING (optimized for weak hardware)
# ============================================================================
# Scan interval in seconds
# HFT: 0.05s = 50ms scan cycle (20 scans/s) for maximum opportunity capture
# Phase 4: High frequency scanner requirement
SCAN_INTERVAL_SEC = _get_env_float("ARB_SCAN_INTERVAL_SEC", 0.05)

# Monitoring output interval in seconds (reduce log spam)
# AGGRESSIVE: 30s for more frequent status updates
# Was: 60s, reduced to 30s for better monitoring
MONITOR_INTERVAL_SEC = _get_env_float("ARB_MONITOR_INTERVAL_SEC", 30.0)

# Enable event-driven scanning (only scan when orderbook changes)
# Reduces CPU usage significantly
EVENT_DRIVEN_SCAN = _get_env_bool("ARB_EVENT_DRIVEN_SCAN", True)

# Minimum time between scans for same symbol (throttle)
MIN_SCAN_INTERVAL_PER_SYMBOL_SEC = _get_env_float("ARB_MIN_SCAN_INTERVAL_PER_SYMBOL", 0.1)

# ============================================================================
# WEBSOCKET RELIABILITY
# ============================================================================
# Enable automatic reconnection on WebSocket disconnect
WS_AUTO_RECONNECT = _get_env_bool("ARB_WS_AUTO_RECONNECT", True)

# Initial reconnect delay in seconds
WS_RECONNECT_DELAY_SEC = _get_env_float("ARB_WS_RECONNECT_DELAY", 5.0)

# Maximum reconnect delay in seconds (exponential backoff cap)
WS_MAX_RECONNECT_DELAY_SEC = _get_env_float("ARB_WS_MAX_RECONNECT_DELAY", 300.0)

# Reconnect backoff multiplier
WS_RECONNECT_BACKOFF_MULTIPLIER = _get_env_float("ARB_WS_BACKOFF_MULTIPLIER", 2.0)

# Maximum number of reconnect attempts (0 = unlimited)
WS_MAX_RECONNECT_ATTEMPTS = _get_env_int("ARB_WS_MAX_RECONNECT_ATTEMPTS", 0)

# Stream staleness threshold in seconds (watchdog)
# Alert if no updates received for this duration
STREAM_STALENESS_THRESHOLD_SEC = _get_env_float("ARB_STREAM_STALENESS_SEC", 60.0)

# Health check interval in seconds
HEALTH_CHECK_INTERVAL_SEC = _get_env_float("ARB_HEALTH_CHECK_INTERVAL", 30.0)

# ============================================================================
# WINDOWS 11 OPTIMIZATION (W4: Resource Monitoring)
# ============================================================================
CPU_CHECK_INTERVAL_SEC = _get_env_float("ARB_CPU_CHECK_INTERVAL", 5.0)
CPU_HIGH_THRESHOLD = _get_env_float("ARB_CPU_HIGH_THRESHOLD", 60.0)  # Reduce activity above this
CPU_CRITICAL_THRESHOLD = _get_env_float("ARB_CPU_CRITICAL_THRESHOLD", 80.0)  # Emergency mode
CPU_LOW_THRESHOLD = _get_env_float("ARB_CPU_LOW_THRESHOLD", 30.0)  # Can increase activity
MEMORY_MAX_MB = _get_env_int("ARB_MEMORY_MAX_MB", 512)  # Target max memory usage

# ============================================================================
# AUTO-REBALANCING (Strategy A3)
# ============================================================================
REBALANCE_INTERVAL_SEC = _get_env_float("ARB_REBALANCE_INTERVAL_SEC", 600)  # 10 minutes (Phase 27)
REBALANCE_MIN_THRESHOLD = _get_env_float("ARB_REBALANCE_MIN_THRESHOLD", 0.15)  # <15% triggers rebalance
REBALANCE_MAX_THRESHOLD = _get_env_float("ARB_REBALANCE_MAX_THRESHOLD", 0.30)  # >30% is source
REBALANCE_MIN_AMOUNT = _get_env_float("ARB_REBALANCE_MIN_AMOUNT", 50.0)  # Min transfer amount

# ============================================================================
# VOLATILITY MONITORING (Strategy S4)
# ============================================================================
VOLATILITY_ATR_WINDOW_SEC = _get_env_int("ARB_VOLATILITY_ATR_WINDOW", 60)  # 1-minute window
VOLATILITY_CALM_THRESHOLD = _get_env_float("ARB_VOLATILITY_CALM_THRESHOLD", 0.5)
VOLATILITY_STORM_MULTIPLIER = _get_env_float("ARB_VOLATILITY_STORM_MULTIPLIER", 3.0)

# ============================================================================
# FUNDING RATE / CROSS-EXCHANGE PREMIUM ARBITRAGE (Strategy S3)
# ============================================================================
# NOTE: This strategy detects cross-exchange price PREMIUMS (price deviations
# between exchanges) — NOT true spot-perpetual funding rate arbitrage.
# True funding arb would require: long spot + short perpetual + collect funding.
# This is more accurately "Premium Arbitrage" but kept as FUNDING_RATE for
# backward compatibility with existing signal/logging infrastructure.
FUNDING_MIN_RATE_PCT = _get_env_float("ARB_FUNDING_MIN_RATE", 0.03)  # Enter at 0.03%
FUNDING_EXIT_RATE_PCT = _get_env_float("ARB_FUNDING_EXIT_RATE", 0.01)  # Exit at 0.01%
FUNDING_CHECK_INTERVAL_SEC = _get_env_float("ARB_FUNDING_CHECK_INTERVAL", 300)  # 5 minutes

# ============================================================================
# TRIANGULAR ARBITRAGE (Strategy S2)
# ============================================================================
TRIANGULAR_MIN_PROFIT_PCT = _get_env_float("ARB_TRIANGULAR_MIN_PROFIT", 0.0005)  # 0.05%
TRIANGULAR_ENABLED = _get_env_bool("ARB_TRIANGULAR_ENABLED", True)

# ============================================================================
# STRATEGY MANAGEMENT (L2)
# ============================================================================
STRATEGY_WINDOW_SIZE = _get_env_int("ARB_STRATEGY_WINDOW", 100)  # Trades to track per strategy
STRATEGY_SWITCH_THRESHOLD = _get_env_float("ARB_STRATEGY_SWITCH_THRESHOLD", 0.1)  # 10% difference

# ============================================================================
# EXCHANGE PARAMETERS
# ============================================================================
# Symbols to trade (can be extended)
# Trading symbols (comma-separated, no spaces)
# Expanded to 46 pairs for maximum opportunity detection
TRADING_SYMBOLS = _get_env_str("ARB_SYMBOLS", (
    "BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT,XRP-USDT,"
    "DOGE-USDT,LTC-USDT,ADA-USDT,MATIC-USDT,DOT-USDT,"
    "LINK-USDT,AVAX-USDT,UNI-USDT,ATOM-USDT,FIL-USDT,"
    "APT-USDT,ARB-USDT,OP-USDT,TRX-USDT,NEAR-USDT,"
    "ETC-USDT,SUI-USDT,INJ-USDT,ICP-USDT,HBAR-USDT,"
    "VET-USDT,ALGO-USDT,AAVE-USDT,CRV-USDT,SNX-USDT,"
    "RUNE-USDT,FTM-USDT,FLOW-USDT,CHZ-USDT,GALA-USDT,"
    "SAND-USDT,AXS-USDT,PEPE-USDT,SHIB-USDT,FLOKI-USDT,"
    "BLUR-USDT,GMX-USDT,DYDX-USDT,ENS-USDT,LDO-USDT,"
    "STX-USDT"
)).split(",")

# Top-K orderbook levels to consider for liquidity
ORDERBOOK_TOP_K = _get_env_int("ARB_ORDERBOOK_TOP_K", 20)

# Default quantity for fallback (in base asset)
DEFAULT_QUANTITY = _get_env_float("ARB_DEFAULT_QUANTITY", 0.001)

# ============================================================================
# LOGGING & PERSISTENCE
# ============================================================================
# Path to persist detected arbitrage opportunities
OPPORTUNITIES_CSV_PATH = _get_env_str("ARB_OPPORTUNITIES_CSV", "arbs.csv")

# Path to persist executed trades
TRADES_CSV_PATH = _get_env_str("ARB_TRADES_CSV", "trades.csv")

# Persistent state file
STATE_FILE_PATH = _get_env_str("ARB_STATE_FILE", "bot_state.json")

# Watchdog heartbeat file
HEARTBEAT_FILE_PATH = _get_env_str("ARB_HEARTBEAT_FILE", "heartbeat.txt")

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL = _get_env_str("ARB_LOG_LEVEL", "INFO")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_config() -> dict:
    """Get configuration as dictionary."""
    return {
        'DRY_RUN': DRY_RUN,
        'MIN_NET_ROI_PCT': MIN_NET_ROI_PCT,
        'MAX_EXPOSURE_USDT': MAX_EXPOSURE_USDT,
        'TRADING_SYMBOLS': TRADING_SYMBOLS,
        'SCAN_INTERVAL_SEC': SCAN_INTERVAL_SEC,
        'SYMBOL_COOLDOWN_SEC': PER_SYMBOL_COOLDOWN_SEC,
        'EXCHANGES': ['Bybit', 'KuCoin', 'HTX', 'MEXC', 'Binance'],
        'MAX_DAILY_LOSS': MAX_DAILY_LOSS,
        'MAX_HOURLY_LOSS': MAX_HOURLY_LOSS,
        'MAX_SINGLE_TRADE_LOSS': MAX_SINGLE_TRADE_LOSS,
        'MAX_CONSECUTIVE_LOSSES': MAX_CONSECUTIVE_LOSSES,
        'MAX_OPEN_EXPOSURE': MAX_OPEN_EXPOSURE,
        'ANOMALOUS_SPREAD_PCT': ANOMALOUS_SPREAD_PCT,
        'MAX_DATA_AGE_SEC': MAX_DATA_AGE_SEC,
    }


def get_config_summary() -> str:
    """Returns a formatted summary of current configuration."""
    return """
=== Arbitrage Bot Configuration (ENHANCED) ===
Execution Mode: {mode}
Exchanges: Bybit, KuCoin, HTX, MEXC, Binance (5 total)
Min Net ROI: {roi}%
Max Exposure: ${exp} USDT
Safety Factor: {sf}
Max Trades/Min: {trades}
Symbol Cooldown: {cool}s (reduced from 30s)
Scan Interval: {scan}s
Event-Driven: {event}
Max Daily Loss: ${daily_loss}
Max Hourly Loss: ${hourly_loss}
WS Auto-Reconnect: {ws}
Trading Symbols: {syms} pairs
Triangular Arb: {triang}
Funding Arb: Enabled
CPU Monitoring: Enabled (threshold: {cpu}%)
Auto-Rebalancing: Every {rebal}min
===================================
""".format(
        mode='🔵 DRY RUN (Safe)' if DRY_RUN else '🔴 LIVE TRADING (Real money!)',
        roi=MIN_NET_ROI_PCT,
        exp=MAX_EXPOSURE_USDT,
        sf=SAFETY_FACTOR,
        trades=MAX_TRADES_PER_MINUTE,
        cool=PER_SYMBOL_COOLDOWN_SEC,
        scan=SCAN_INTERVAL_SEC,
        event=EVENT_DRIVEN_SCAN,
        daily_loss=MAX_DAILY_LOSS,
        hourly_loss=MAX_HOURLY_LOSS,
        ws=WS_AUTO_RECONNECT,
        syms=len(TRADING_SYMBOLS),
        triang='Enabled' if TRIANGULAR_ENABLED else 'Disabled',
        cpu=CPU_HIGH_THRESHOLD,
        rebal=REBALANCE_INTERVAL_SEC / 60
    )


def validate_api_keys() -> tuple[bool, List[str]]:
    """Validate that all required API keys are set for live trading."""
    issues = []
    
    if not DRY_RUN:
        # Check all exchange API keys
        if not BYBIT_API_KEY or not BYBIT_API_SECRET:
            issues.append("⚠️  Bybit API keys not set")
        if not KUCOIN_API_KEY or not KUCOIN_API_SECRET or not KUCOIN_PASSPHRASE:
            issues.append("⚠️  KuCoin API keys not set")
        if not HTX_API_KEY or not HTX_API_SECRET:
            issues.append("⚠️  HTX API keys not set")
        if not MEXC_API_KEY or not MEXC_API_SECRET:
            issues.append("⚠️  MEXC API keys not set")
        if not BINANCE_API_KEY or not BINANCE_API_SECRET:
            issues.append("⚠️  Binance API keys not set")
    
    return len(issues) == 0, issues


def is_production_ready() -> tuple[bool, List[str]]:
    """Check if configuration is safe for production."""
    issues = []
    
    if not DRY_RUN:
        issues.append("⚠️  DRY_RUN is disabled - bot will place REAL orders!")
        
        # Validate API keys
        keys_valid, key_issues = validate_api_keys()
        if not keys_valid:
            issues.extend(key_issues)
    
    if MIN_NET_ROI_PCT < 0.05:
        issues.append(f"⚠️  MIN_NET_ROI_PCT ({MIN_NET_ROI_PCT}%) is very low - may result in unprofitable trades")
    
    if MAX_EXPOSURE_USDT > 1000:
        issues.append(f"⚠️  MAX_EXPOSURE_USDT (${MAX_EXPOSURE_USDT}) is quite high")
    
    if SAFETY_FACTOR > 0.8:
        issues.append(f"⚠️  SAFETY_FACTOR ({SAFETY_FACTOR}) is high - may cause slippage")
    
    if MAX_DAILY_LOSS > 100:
        issues.append(f"⚠️  MAX_DAILY_LOSS (${MAX_DAILY_LOSS}) is quite high")
    
    return len(issues) == 0, issues


if __name__ == "__main__":
    # Print configuration when run directly
    print(get_config_summary())
    ready, issues = is_production_ready()
    if not ready:
        print("\n⚠️  Configuration Issues:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n✅ Configuration looks safe")
