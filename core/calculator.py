"""
Полный модуль расчётов прибыли и метрик для арбитража.
"""
import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)


class ProfitCalculator:
    """Калькулятор прибыли для арбитражных операций."""
    
    def __init__(self):
        """Инициализация калькулятора."""
        self.logger = logging.getLogger(__name__)
    
    def calculate_profit(
        self,
        buy_price: float,
        sell_price: float,
        buy_fee: float,
        sell_fee: float,
        amount: float
    ) -> Dict[str, float]:
        """
        Рассчитать прибыль от арбитражной сделки.
        
        Args:
            buy_price: Цена покупки
            sell_price: Цена продажи
            buy_fee: Комиссия при покупке (в процентах)
            sell_fee: Комиссия при продаже (в процентах)
            amount: Объём в USDT
            
        Returns:
            Словарь с метриками прибыли
        """
        try:
            # Расчёт стоимости с учётом комиссий
            buy_cost = amount * (1 + buy_fee / 100)
            crypto_amount = amount / buy_price
            sell_revenue = crypto_amount * sell_price * (1 - sell_fee / 100)
            
            # Чистая прибыль
            net_profit = sell_revenue - buy_cost
            profit_percent = (net_profit / buy_cost) * 100 if buy_cost > 0 else 0
            
            return {
                'buy_cost': buy_cost,
                'sell_revenue': sell_revenue,
                'net_profit': net_profit,
                'profit_percent': profit_percent,
                'crypto_amount': crypto_amount,
                'effective_buy_price': buy_cost / crypto_amount if crypto_amount > 0 else 0,
                'effective_sell_price': sell_revenue / crypto_amount if crypto_amount > 0 else 0
            }
        except Exception as e:
            self.logger.error(f"Error calculating profit: {e}")
            return {}
    
    def calculate_roi(self, initial_investment: float, final_value: float) -> float:
        """Рассчитать ROI (Return on Investment)."""
        if initial_investment <= 0:
            return 0.0
        return ((final_value - initial_investment) / initial_investment) * 100
    
    def calculate_breakeven_price(
        self,
        buy_price: float,
        buy_fee: float,
        sell_fee: float
    ) -> float:
        """Рассчитать цену безубыточности."""
        total_fee_percent = (buy_fee + sell_fee) / 100
        return buy_price * (1 + total_fee_percent) / (1 - total_fee_percent)
    
    def calculate_optimal_position_size(
        self,
        capital: float,
        risk_percent: float,
        expected_profit_percent: float
    ) -> float:
        """Рассчитать оптимальный размер позиции."""
        risk_amount = capital * (risk_percent / 100)
        if expected_profit_percent > 0:
            return risk_amount / (expected_profit_percent / 100)
        return 0.0
    
    def calculate_slippage(
        self,
        expected_price: float,
        actual_price: float
    ) -> Dict[str, float]:
        """Рассчитать slippage."""
        slippage_abs = actual_price - expected_price
        slippage_percent = (slippage_abs / expected_price) * 100 if expected_price > 0 else 0
        
        return {
            'slippage_abs': slippage_abs,
            'slippage_percent': slippage_percent,
            'expected_price': expected_price,
            'actual_price': actual_price
        }
    
    def calculate_effective_fee(
        self,
        buy_fee: float,
        sell_fee: float,
        price_change_percent: float = 0
    ) -> float:
        """Рассчитать эффективную комиссию с учётом изменения цены."""
        base_fee = buy_fee + sell_fee
        price_impact = abs(price_change_percent)
        return base_fee + price_impact


def calculate_arbitrage_profit(
    buy_exchange: str,
    sell_exchange: str,
    buy_price: float,
    sell_price: float,
    buy_fee: float,
    sell_fee: float,
    amount_usdt: float
) -> Dict[str, float]:
    """
    Вспомогательная функция для быстрого расчёта арбитражной прибыли.
    """
    calculator = ProfitCalculator()
    result = calculator.calculate_profit(buy_price, sell_price, buy_fee, sell_fee, amount_usdt)
    result['buy_exchange'] = buy_exchange
    result['sell_exchange'] = sell_exchange
    return result
