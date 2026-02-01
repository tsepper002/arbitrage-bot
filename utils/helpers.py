def calculate_profit(buy_price, sell_price, buy_fee, sell_fee, amount_usdt):
    buy_amount = amount_usdt / buy_price
    sell_amount = buy_amount * sell_price
    profit = sell_amount - amount_usdt
    fee = profit * (buy_fee + sell_fee) / 100
    return profit - fee
