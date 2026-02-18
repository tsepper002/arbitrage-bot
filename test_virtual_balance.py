#!/usr/bin/env python3
"""Quick test to show virtual balance display"""
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Mock settings
class Settings:
    DRY_RUN = True
    MIN_BALANCE_PER_EXCHANGE = 8.0

import sys
sys.modules['settings'] = Settings()

# Test the balance display
mock_balance = {
    'USDT': 30.0,
    'BTC': 0.0005,
    'ETH': 0.005,
    'BNB': 0.05,
    'SOL': 0.2
}

exchanges = ['Bybit', 'KuCoin', 'HTX', 'MEXC']

logger = logging.getLogger(__name__)
logger.info("=" * 70)
logger.info("🔵 DRY_RUN MODE - VIRTUAL BALANCES")
logger.info("=" * 70)

for exchange_name in exchanges:
    balance = mock_balance.copy()
    total = sum(balance.get(curr, 0) * price for curr, price in [
        ('USDT', 1.0), ('BTC', 68500), ('ETH', 3500), 
        ('BNB', 350), ('SOL', 85)
    ])
    usdt = balance.get('USDT', 0)
    logger.info(f"  {exchange_name:12} | USDT: ${usdt:>8.2f} | Total: ${total:>8.2f} (VIRTUAL)")

total_capital = len(exchanges) * sum(mock_balance.get(curr, 0) * price for curr, price in [
    ('USDT', 1.0), ('BTC', 68500), ('ETH', 3500), 
    ('BNB', 350), ('SOL', 85)
])
logger.info("=" * 70)
logger.info(f"💰 Total Virtual Capital: ${total_capital:.2f}")
logger.info("=" * 70)
logger.info("")
logger.info("📊 В DRY_RUN РЕЖИМЕ:")
logger.info("   • Используются виртуальные деньги")
logger.info("   • Сделки симулируются")
logger.info("   • Можно безопасно тестировать все 14 стратегий")
logger.info("   • Виртуальный профит будет отображаться в логах")
logger.info("")
