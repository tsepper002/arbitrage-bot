#!/usr/bin/env python3
"""
Configuration settings for the arbitrage bot.
All settings have safe, conservative defaults suitable for initial testing.
Override via environment variables or by modifying defaults below.
"""
import os
from typing import Optional


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


# ============================================================================
# ORDER EXECUTION MODE
# ============================================================================
# CRITICAL: Set to True only when ready for real trading with funded accounts
# Default is False for safety - all orders will be simulated
DRY_RUN = _get_env_bool("ARB_DRY_RUN", True)

# Starting virtual capital for dry run mode (USDT)
VIRTUAL_CAPITAL_USDT = _get_env_float("ARB_VIRTUAL_CAPITAL_USDT", 10000.0)

# ============================================================================
# RISK MANAGEMENT PARAMETERS
# ============================================================================
# Minimum net ROI percentage required to execute trade (after fees & slippage)
MIN_NET_ROI_PCT = _get_env_float("ARB_MIN_NET_ROI_PCT", 0.05)

# Maximum exposure per trade in USDT (conservative default)
MAX_EXPOSURE_USDT = _get_env_float("ARB_MAX_EXPOSURE_USDT", 200.0)

# Safety factor for liquidity (use only this fraction of available liquidity)
# 0.5 = use max 50% of available liquidity to avoid slippage
SAFETY_FACTOR = _get_env_float("ARB_SAFETY_FACTOR", 0.5)

# Maximum number of trades per minute (rate limiting)
MAX_TRADES_PER_MINUTE = _get_env_int("ARB_MAX_TRADES_PER_MINUTE", 5)

# Cooldown period in seconds before same symbol can be traded again
PER_SYMBOL_COOLDOWN_SEC = _get_env_float("ARB_SYMBOL_COOLDOWN_SEC", 30.0)

# Maximum concurrent opportunities to process per scan cycle
MAX_CONCURRENT_OPPORTUNITIES = _get_env_int("ARB_MAX_CONCURRENT_OPPS", 3)

# ============================================================================
# PERFORMANCE & THROTTLING (optimized for weak hardware)
# ============================================================================
# Scan interval in seconds (increase on weak hardware)
SCAN_INTERVAL_SEC = _get_env_float("ARB_SCAN_INTERVAL_SEC", 1.0)

# Monitoring output interval in seconds (reduce log spam)
MONITOR_INTERVAL_SEC = _get_env_float("ARB_MONITOR_INTERVAL_SEC", 5.0)

# Enable event-driven scanning (only scan when orderbook changes)
# Reduces CPU usage significantly
EVENT_DRIVEN_SCAN = _get_env_bool("ARB_EVENT_DRIVEN_SCAN", True)

# Minimum time between scans for same symbol (throttle)
MIN_SCAN_INTERVAL_PER_SYMBOL_SEC = _get_env_float("ARB_MIN_SCAN_INTERVAL_PER_SYMBOL", 0.5)

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
# EXCHANGE PARAMETERS
# ============================================================================
# Symbols to trade (can be extended)
TRADING_SYMBOLS = os.getenv("ARB_SYMBOLS", "BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT,XRP-USDT,DOGE-USDT,LTC-USDT,ADA-USDT,MATIC-USDT,DOT-USDT").split(",")

# Top-K orderbook levels to consider for liquidity
ORDERBOOK_TOP_K = _get_env_int("ARB_ORDERBOOK_TOP_K", 20)

# Default quantity for fallback (in base asset)
DEFAULT_QUANTITY = _get_env_float("ARB_DEFAULT_QUANTITY", 0.001)

# ============================================================================
# LOGGING & PERSISTENCE
# ============================================================================
# Path to persist detected arbitrage opportunities
OPPORTUNITIES_CSV_PATH = os.getenv("ARB_OPPORTUNITIES_CSV", "arbs.csv")

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL = os.getenv("ARB_LOG_LEVEL", "INFO")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def get_config_summary() -> str:
    """Returns a formatted summary of current configuration."""
    return """
=== Arbitrage Bot Configuration ===
Execution Mode: {mode}
Virtual Capital: ${vcap} USDT
Min Net ROI: {roi}%
Max Exposure: ${exp} USDT
Safety Factor: {sf}
Max Trades/Min: {trades}
Symbol Cooldown: {cool}s
Scan Interval: {scan}s
Event-Driven: {event}
WS Auto-Reconnect: {ws}
Stream Staleness Threshold: {stale}s
Trading Symbols: {syms} pairs
===================================
""".format(
        mode='DRY RUN (Safe)' if DRY_RUN else 'LIVE TRADING (Real money!)',
        vcap=VIRTUAL_CAPITAL_USDT if DRY_RUN else 'N/A',
        roi=MIN_NET_ROI_PCT,
        exp=MAX_EXPOSURE_USDT,
        sf=SAFETY_FACTOR,
        trades=MAX_TRADES_PER_MINUTE,
        cool=PER_SYMBOL_COOLDOWN_SEC,
        scan=SCAN_INTERVAL_SEC,
        event=EVENT_DRIVEN_SCAN,
        ws=WS_AUTO_RECONNECT,
        stale=STREAM_STALENESS_THRESHOLD_SEC,
        syms=len(TRADING_SYMBOLS)
    )


def is_production_ready() -> bool:
    """Check if configuration is safe for production."""
    issues = []
    
    if not DRY_RUN:
        issues.append("⚠️  DRY_RUN is disabled - bot will place REAL orders!")
    
    if MIN_NET_ROI_PCT < 0.05:
        issues.append(f"⚠️  MIN_NET_ROI_PCT ({MIN_NET_ROI_PCT}%) is very low - may result in unprofitable trades")
    
    if MAX_EXPOSURE_USDT > 1000:
        issues.append(f"⚠️  MAX_EXPOSURE_USDT (${MAX_EXPOSURE_USDT}) is quite high")
    
    if SAFETY_FACTOR > 0.8:
        issues.append(f"⚠️  SAFETY_FACTOR ({SAFETY_FACTOR}) is high - may cause slippage")
    
    if issues:
        return False, issues
    
    return True, []


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
