# Configuration and helpers for exchange fees and parameters.
# You can extend this file or load values from a JSON/YAML file or environment variables.

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
        "min_notional": 10.0,  # Binance has higher min notional
        "min_size": 0.0001,
        "supports_depth": True,
    },
}

# Optionally try to refresh fees via REST public/private APIs.
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