# Конфиг комиссий/параметров бирж — BASE TIER (no VIP, no exchange tokens)
# Last verified: Feb 2026
EXCHANGE_PARAMS = {
    "Bybit": {
        "maker": 0.001,    # 0.10%
        "taker": 0.001,    # 0.10%
        "withdraw_fee": 1.6,
        "withdraw_fee_currency": "USDT",
        "min_notional": 1.0,
        "min_size": 0.0001,
    },
    "KuCoin": {
        "maker": 0.001,    # 0.10%
        "taker": 0.001,    # 0.10%
        "withdraw_fee": 1.5,
        "withdraw_fee_currency": "USDT",
        "min_notional": 1.0,
        "min_size": 0.0001,
    },
    "HTX": {
        "maker": 0.002,    # 0.20%
        "taker": 0.002,    # 0.20%
        "withdraw_fee": 1.25,
        "withdraw_fee_currency": "USDT",
        "min_notional": 1.0,
        "min_size": 0.0001,
    },
    "MEXC": {
        "maker": 0.000,    # 0.00% (free for all)
        "taker": 0.0005,   # 0.05%
        "withdraw_fee": 1.0,
        "withdraw_fee_currency": "USDT",
        "min_notional": 1.0,
        "min_size": 0.0001,
    },
    "Binance": {
        "maker": 0.001,    # 0.10%
        "taker": 0.001,    # 0.10%
        "withdraw_fee": 1.0,
        "withdraw_fee_currency": "USDT",
        "min_notional": 10.0,
        "min_size": 0.0001,
    },
}