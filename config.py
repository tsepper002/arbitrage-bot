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