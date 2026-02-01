# Configuration and helpers for exchange fees and parameters.
# You can extend this file or load values from a JSON/YAML file or environment variables.

import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("exchange_config")

# Default static parameters. You should validate and update these for your accounts.
EXCHANGE_PARAMS: Dict[str, Dict[str, Any]] = {
    "Bybit": {
        "maker": 0.0002,
        "taker": 0.0006,
        "withdraw_fee": None,
        "withdraw_fee_currency": "USDT",
        "min_notional": 1.0,
        "min_size": 0.0001,
        "supports_depth": False,  # enable true if you implemented depth parsing
    },
    "KuCoin": {
        "maker": 0.0001,
        "taker": 0.0006,
        "withdraw_fee": None,
        "withdraw_fee_currency": "USDT",
        "min_notional": 1.0,
        "min_size": 0.0001,
        "supports_depth": False,
    },
    "HTX": {
        "maker": 0.0000,
        "taker": 0.0020,
        "withdraw_fee": None,
        "withdraw_fee_currency": "USDT",
        "min_notional": 1.0,
        "min_size": 0.0001,
        "supports_depth": False,
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