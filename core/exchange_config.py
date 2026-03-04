# Configuration and helpers for exchange fees and parameters.
# You can extend this file or load values from a JSON/YAML file or environment variables.

import math
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("exchange_config")

# ============================================================
# SPOT TRADING FEES — BASE TIER (no VIP, no exchange tokens)
# Last verified: Feb 2026
# User conditions: no BNB/KCS/MX holdings, no VIP status
# ============================================================
EXCHANGE_PARAMS: Dict[str, Dict[str, Any]] = {
    "Bybit": {
        "maker": 0.001,    # 0.10% maker fee (base tier, no VIP)
        "taker": 0.001,    # 0.10% taker fee (base tier, no VIP)
        "withdraw_fee": 1.6,  # USDT TRC20 withdrawal fee
        "withdraw_fee_currency": "USDT",
        "withdraw_network": "TRC20",
        "min_notional": 1.0,
        "min_size": 0.0001,
        "supports_depth": True,
    },
    "KuCoin": {
        "maker": 0.001,    # 0.10% maker fee (base tier, no KCS discount)
        "taker": 0.001,    # 0.10% taker fee (base tier, no KCS discount)
        "withdraw_fee": 1.5,  # USDT TRC20 withdrawal fee
        "withdraw_fee_currency": "USDT",
        "withdraw_network": "TRC20",
        "min_notional": 1.0,
        "min_size": 0.0001,
        "supports_depth": True,
    },
    "HTX": {
        "maker": 0.002,    # 0.20% maker fee (base tier)
        "taker": 0.002,    # 0.20% taker fee (base tier)
        "withdraw_fee": 1.25, # USDT TRC20 withdrawal fee
        "withdraw_fee_currency": "USDT",
        "withdraw_network": "TRC20",
        "min_notional": 1.0,
        "min_size": 0.0001,
        "supports_depth": True,
    },
    "MEXC": {
        "maker": 0.000,    # 0.00% maker fee (free for all users)
        "taker": 0.0005,   # 0.05% taker fee (base tier, no MX token discount)
        "withdraw_fee": 1.0,  # USDT TRC20 withdrawal fee
        "withdraw_fee_currency": "USDT",
        "withdraw_network": "TRC20",
        "min_notional": 1.0,
        "min_size": 0.0001,
        "supports_depth": True,
    },
    "Binance": {
        "maker": 0.001,    # 0.10% maker fee (base tier, no BNB discount)
        "taker": 0.001,    # 0.10% taker fee (base tier, no BNB discount)
        "withdraw_fee": 1.0,  # USDT TRC20 withdrawal fee
        "withdraw_fee_currency": "USDT",
        "withdraw_network": "TRC20",
        "min_notional": 5.0,  # Binance spot MARKET orders: $5 min (LIMIT: $5 also)
        "min_size": 0.0001,
        "supports_depth": True,
    },
}

# ============================================================
# PER-PAIR TRADING RULES (lot_size, tick_size, min_notional)
# Static defaults — exchanges use these for order validation
# ============================================================
PAIR_RULES: Dict[str, Dict[str, Any]] = {}
# Populated by load_pair_rules() at startup

# Default rules when not loaded from exchange
_DEFAULT_PAIR_RULES = {
    "step_size": 0.01,       # qty increment
    "tick_size": 0.0001,     # price increment
    "min_qty": 0.01,
    "min_notional": 5.0,     # minimum order value in USDT
}

# Known step_sizes per coin (Binance spot, as of Feb 2026)
_KNOWN_STEP_SIZES = {
    "BTC": 0.00001, "ETH": 0.0001, "SOL": 0.01, "XRP": 0.1,
    "DOGE": 1.0, "DOT": 0.01, "AVAX": 0.01, "NEAR": 0.1,
    "ATOM": 0.01, "FIL": 0.01, "APT": 0.01, "ARB": 0.1,
    "OP": 0.01, "LINK": 0.01, "UNI": 0.01, "ADA": 0.1,
    "LTC": 0.001, "BNB": 0.001, "TRX": 0.1,
}

_KNOWN_TICK_SIZES = {
    "BTC": 0.01, "ETH": 0.01, "SOL": 0.01, "XRP": 0.0001,
    "DOGE": 0.00001, "DOT": 0.001, "AVAX": 0.001, "NEAR": 0.0001,
    "ATOM": 0.001, "FIL": 0.001, "APT": 0.0001, "ARB": 0.0001,
    "OP": 0.0001, "LINK": 0.001, "UNI": 0.001, "ADA": 0.0001,
    "LTC": 0.01, "BNB": 0.01, "TRX": 0.0001,
}

_KNOWN_MIN_NOTIONAL = {
    "Binance": 5.0, "MEXC": 1.0, "KuCoin": 0.1, "Bybit": 1.0, "HTX": 5.0,
}


def get_pair_rules(exchange: str, symbol: str) -> Dict[str, Any]:
    """Get trading rules for a specific exchange+symbol pair.
    
    Returns dict with: step_size, tick_size, min_qty, min_notional
    """
    # Try loaded rules first
    key = f"{exchange}:{symbol}"
    if key in PAIR_RULES:
        return PAIR_RULES[key]
    
    # Fall back to known static values
    base = symbol.split("-")[0] if "-" in symbol else symbol.split("/")[0]
    return {
        "step_size": _KNOWN_STEP_SIZES.get(base, _DEFAULT_PAIR_RULES["step_size"]),
        "tick_size": _KNOWN_TICK_SIZES.get(base, _DEFAULT_PAIR_RULES["tick_size"]),
        "min_qty": _DEFAULT_PAIR_RULES["min_qty"],
        "min_notional": _KNOWN_MIN_NOTIONAL.get(exchange, _DEFAULT_PAIR_RULES["min_notional"]),
    }


def round_qty(exchange: str, symbol: str, qty: float) -> float:
    """Round quantity DOWN to exchange step_size.

    Uses round() to clean up floating-point artifacts.
    E.g. math.floor(5.89/0.01)*0.01 = 5.890000000000001 → round → 5.89
    """
    rules = get_pair_rules(exchange, symbol)
    step = rules["step_size"]
    if step <= 0:
        return qty
    # Calculate decimal places from step size for clean rounding
    decimals = max(0, -math.floor(math.log10(step))) if step < 1 else 0
    result = math.floor(qty / step) * step
    return round(result, decimals)


def round_price(exchange: str, symbol: str, price: float) -> float:
    """Round price to exchange tick_size."""
    rules = get_pair_rules(exchange, symbol)
    tick = rules["tick_size"]
    if tick <= 0:
        return price
    return round(price / tick) * tick
# Implemented as best-effort: networks and endpoints change over time.
def fetch_kucoin_fees() -> Optional[Dict[str, Any]]:
    """
    Example: KuCoin may expose fee info via REST for certain account types.
    This is optional, best-effort; keep static EXCHANGE_PARAMS as fallback.
    """
    try:
        # KuCoin does not provide a simple public fees endpoint for everyone;
        # this is a placeholder to illustrate dynamic loading.
        r = requests.get("https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT", timeout=5)
        if r.ok:
            return {"note": "fetched sample endpoint; not fee data"}
    except Exception as e:
        logger.debug("KuCoin fee fetch failed: %s", e)
    return None


def try_refresh_params():
    """
    Hook to attempt refreshing fee parameters from exchanges if possible.
    Call this at startup or periodically.
    """
    try:
        ku = fetch_kucoin_fees()
        if ku:
            logger.debug("KuCoin dynamic info: %s", ku)
    except Exception:
        logger.exception("Error refreshing exchange params")