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
# Minimum percentage ROI after fees to consider executing (0.05 = 0.05%)
# Lowered from 0.05 to 0.03 for more trading opportunities
MIN_NET_ROI_PCT = _get_env_float("ARB_MIN_NET_ROI_PCT", 0.03)

# Maximum exposure per trade in USDT (conservative default)
# Increased from 200 to 500 for higher profit potential per trade
MAX_EXPOSURE_USDT = _get_env_float("ARB_MAX_EXPOSURE_USDT", 500.0)

# Safety factor for liquidity (use only this fraction of available liquidity)
# 0.5 = use max 50% of available liquidity to avoid slippage
SAFETY_FACTOR = _get_env_float("ARB_SAFETY_FACTOR", 0.5)

# Maximum number of trades per minute (rate limiting)
MAX_TRADES_PER_MINUTE = _get_env_int("ARB_MAX_TRADES_PER_MINUTE", 5)

# Cooldown period in seconds before same symbol can be traded again
# Reduced from 30 to 3 for more frequent trading on same pairs
PER_SYMBOL_COOLDOWN_SEC = _get_env_float("ARB_SYMBOL_COOLDOWN_SEC", 3.0)
SYMBOL_COOLDOWN_SEC = PER_SYMBOL_COOLDOWN_SEC  # Alias for compatibility

# Maximum concurrent opportunities to process per scan cycle
MAX_CONCURRENT_OPPORTUNITIES = _get_env_int("ARB_MAX_CONCURRENT_OPPS", 3)

# ============================================================================
# MULTI-LAYER RISK LIMITS (Strategy A5)
# ============================================================================
MAX_DAILY_LOSS = _get_env_float("ARB_MAX_DAILY_LOSS", 50.0)  # Stop trading if daily loss exceeds this
MAX_SINGLE_TRADE_LOSS = _get_env_float("ARB_MAX_SINGLE_TRADE_LOSS", 15.0)  # Cancel trade if loss exceeds
MAX_HOURLY_LOSS = _get_env_float("ARB_MAX_HOURLY_LOSS", 20.0)  # Pause if hourly loss exceeds
MAX_OPEN_EXPOSURE = _get_env_float("ARB_MAX_OPEN_EXPOSURE", 500.0)  # Max total open position value
MAX_CONSECUTIVE_LOSSES = _get_env_int("ARB_MAX_CONSECUTIVE_LOSSES", 5)  # Pause after N losses
ANOMALOUS_SPREAD_PCT = _get_env_float("ARB_ANOMALOUS_SPREAD_PCT", 5.0)  # Skip spreads above this
MAX_DATA_AGE_SEC = _get_env_float("ARB_MAX_DATA_AGE_SEC", 3.0)  # Don't trade on stale data
MIN_BALANCE_PER_EXCHANGE = _get_env_float("ARB_MIN_BALANCE_PER_EXCHANGE", 20.0)  # Min balance to trade

# ============================================================================
# PERFORMANCE & THROTTLING (optimized for weak hardware)
# ============================================================================
# Scan interval in seconds (reduced from 1.0 to 0.5 for faster reactions)
SCAN_INTERVAL_SEC = _get_env_float("ARB_SCAN_INTERVAL_SEC", 0.5)

# Monitoring output interval in seconds (reduce log spam)
MONITOR_INTERVAL_SEC = _get_env_float("ARB_MONITOR_INTERVAL_SEC", 5.0)

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
MEMORY_MAX_MB = _get_env_int("ARB_MEMORY_MAX_MB", 200)  # Target max memory usage

# ============================================================================
# AUTO-REBALANCING (Strategy A3)
# ============================================================================
REBALANCE_INTERVAL_SEC = _get_env_float("ARB_REBALANCE_INTERVAL_SEC", 1800)  # 30 minutes
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
# FUNDING RATE ARBITRAGE (Strategy S3)
# ============================================================================
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
# Expanded from 10 to 20 pairs for more opportunities
TRADING_SYMBOLS = _get_env_str("ARB_SYMBOLS", "BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT,XRP-USDT,DOGE-USDT,LTC-USDT,ADA-USDT,MATIC-USDT,DOT-USDT,LINK-USDT,AVAX-USDT,UNI-USDT,ATOM-USDT,FIL-USDT,APT-USDT,ARB-USDT,OP-USDT,TRX-USDT,NEAR-USDT").split(",")

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
        'EXCHANGES': ['Bybit', 'KuCoin', 'HTX', 'MEXC'],
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
Exchanges: Bybit, KuCoin, HTX, MEXC (4 total)
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
        if not XT_API_KEY or not XT_API_SECRET:
            issues.append("⚠️  XT API keys not set")
        if not MEXC_API_KEY or not MEXC_API_SECRET:
            issues.append("⚠️  MEXC API keys not set")
    
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
