"""
DEPRECATED: This file is legacy dead code and is no longer used.
The active configuration is in core/exchange_config.py which has updated 2025 fee schedules.
This file can be safely removed.
"""

# Конфиг комиссий/параметров бирж
EXCHANGE_PARAMS = {
    "Bybit": {
        "maker": 0.0002,
        "taker": 0.0006,
        "withdraw_fee": None,
        "withdraw_fee_currency": "USDT",
        "min_notional": 1.0,
        "min_size": 0.0001,
    },
    "KuCoin": {
        "maker": 0.0001,
        "taker": 0.0006,
        "withdraw_fee": None,
        "withdraw_fee_currency": "USDT",
        "min_notional": 1.0,
        "min_size": 0.0001,
    },
    "HTX": {
        "maker": 0.0000,
        "taker": 0.0020,
        "withdraw_fee": None,
        "withdraw_fee_currency": "USDT",
        "min_notional": 1.0,
        "min_size": 0.0001,
    },
}