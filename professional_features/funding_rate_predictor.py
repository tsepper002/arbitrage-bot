"""
Funding Rate Predictor
Предсказывает funding rates для оптимизации carry trades
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class FundingRatePredictor:
    """Предсказание funding rates и оптимизация carry trades"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # История funding rates
        self.funding_history: Dict[str, deque] = {}
        self.history_size = self.config.get('history_size', 24)  # 24 часа
        
        # Параметры предсказания
        self.ewma_alpha = self.config.get('ewma_alpha', 0.3)
        self.prediction_horizon = self.config.get('prediction_horizon', 8)  # 8 часов
        
        # Пороги для торговли
        self.positive_threshold = self.config.get('positive_threshold', 0.01)  # 0.01%
        self.negative_threshold = self.config.get('negative_threshold', -0.01)
        
        # Статистика
        self.predictions: Dict[str, List[float]] = {}
        self.actual_rates: Dict[str, List[float]] = {}
        
        self.stats = {
            'total_predictions': 0,
            'accurate_predictions': 0,
            'carry_trades_opened': 0,
            'total_profit': 0.0
        }
        
        logger.info("FundingRatePredictor initialized")
    
    def add_funding_rate(self, symbol: str, rate: float, timestamp: datetime):
        """Добавить новый funding rate"""
        if symbol not in self.funding_history:
            self.funding_history[symbol] = deque(maxlen=self.history_size)
            self.predictions[symbol] = []
            self.actual_rates[symbol] = []
        
        self.funding_history[symbol].append({
            'rate': rate,
            'timestamp': timestamp
        })
        
        logger.debug(f"Added funding rate for {symbol}: {rate:.4f}%")
    
    def predict_next_rate(self, symbol: str) -> Optional[float]:
        """Предсказать следующий funding rate"""
        if symbol not in self.funding_history or len(self.funding_history[symbol]) < 3:
            return None
        
        history = self.funding_history[symbol]
        rates = [entry['rate'] for entry in history]
        
        # EWMA prediction
        ewma = rates[-1]
        for rate in reversed(rates[:-1]):
            ewma = self.ewma_alpha * rate + (1 - self.ewma_alpha) * ewma
        
        # Trend adjustment
        if len(rates) >= 3:
            recent_trend = (rates[-1] - rates[-3]) / 2
            ewma += recent_trend * 0.5
        
        self.predictions[symbol].append(ewma)
        self.stats['total_predictions'] += 1
        
        return ewma
    
    def calculate_carry_opportunity(self, symbol: str) -> Dict:
        """Рассчитать возможность carry trade"""
        predicted_rate = self.predict_next_rate(symbol)
        
        if predicted_rate is None:
            return {'signal': 'HOLD', 'confidence': 0.0}
        
        history = self.funding_history[symbol]
        if len(history) < 5:
            return {'signal': 'HOLD', 'confidence': 0.0}
        
        recent_rates = [entry['rate'] for entry in list(history)[-5:]]
        avg_rate = statistics.mean(recent_rates)
        volatility = statistics.stdev(recent_rates) if len(recent_rates) > 1 else 0.0
        
        # Сигналы
        signal = 'HOLD'
        confidence = 0.0
        
        if predicted_rate > self.positive_threshold:
            # Short perpetual, long spot (получать funding)
            signal = 'SHORT_PERP_LONG_SPOT'
            confidence = min(predicted_rate / self.positive_threshold, 1.0)
        elif predicted_rate < self.negative_threshold:
            # Long perpetual, short spot (платить negative funding)
            signal = 'LONG_PERP_SHORT_SPOT'
            confidence = min(abs(predicted_rate) / abs(self.negative_threshold), 1.0)
        
        # Adjust confidence based on volatility
        if volatility > 0:
            confidence *= (1 - min(volatility * 100, 0.5))
        
        return {
            'signal': signal,
            'predicted_rate': predicted_rate,
            'current_avg': avg_rate,
            'confidence': confidence,
            'volatility': volatility,
            'expected_profit': abs(predicted_rate) * confidence
        }
    
    def get_optimal_timing(self, symbol: str) -> Dict:
        """Определить оптимальное время для входа/выхода"""
        opportunity = self.calculate_carry_opportunity(symbol)
        
        if opportunity['signal'] == 'HOLD':
            return {'action': 'WAIT', 'reason': 'No opportunity'}
        
        history = self.funding_history[symbol]
        if not history:
            return {'action': 'WAIT', 'reason': 'Insufficient data'}
        
        last_entry = history[-1]
        next_funding_time = last_entry['timestamp'] + timedelta(hours=8)
        time_until_funding = (next_funding_time - datetime.now()).total_seconds() / 3600
        
        # Оптимальное время входа - за 30 минут до funding
        optimal_entry_time = max(time_until_funding - 0.5, 0)
        
        return {
            'action': 'ENTER' if optimal_entry_time < 0.1 else 'WAIT',
            'signal': opportunity['signal'],
            'time_until_funding': time_until_funding,
            'optimal_entry_in': optimal_entry_time,
            'expected_profit': opportunity['expected_profit'],
            'confidence': opportunity['confidence']
        }
    
    def evaluate_prediction_accuracy(self, symbol: str, actual_rate: float):
        """Оценить точность предсказания"""
        if symbol not in self.predictions or not self.predictions[symbol]:
            return
        
        predicted = self.predictions[symbol][-1]
        error = abs(predicted - actual_rate)
        
        self.actual_rates[symbol].append(actual_rate)
        
        # Считаем точным, если ошибка < 20%
        if actual_rate == 0:
            return
        if error / abs(actual_rate) < 0.2:
            self.stats['accurate_predictions'] += 1
        
        if self.stats['total_predictions'] == 0:
            return
        accuracy = self.stats['accurate_predictions'] / self.stats['total_predictions']
        
        logger.info(f"Prediction accuracy for {symbol}: {accuracy:.2%}, error: {error:.4f}%")
    
    def get_statistics(self) -> Dict:
        """Получить статистику"""
        accuracy = 0.0
        if self.stats['total_predictions'] > 0:
            accuracy = self.stats['accurate_predictions'] / self.stats['total_predictions']
        
        return {
            **self.stats,
            'accuracy': accuracy,
            'tracked_symbols': len(self.funding_history)
        }
    
    async def run_analysis(self, symbols: List[str], rate_fetcher) -> List[Dict]:
        """Запустить анализ для списка символов"""
        results = []
        
        for symbol in symbols:
            try:
                # Получить текущий funding rate
                current_rate = await rate_fetcher(symbol)
                self.add_funding_rate(symbol, current_rate, datetime.now())
                
                # Анализ
                opportunity = self.calculate_carry_opportunity(symbol)
                timing = self.get_optimal_timing(symbol)
                
                if opportunity['signal'] != 'HOLD':
                    results.append({
                        'symbol': symbol,
                        'opportunity': opportunity,
                        'timing': timing
                    })
            
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
        
        return results


async def main():
    """Пример использования"""
    predictor = FundingRatePredictor()
    
    # Симуляция добавления данных
    symbol = 'BTCUSDT'
    rates = [0.01, 0.015, 0.02, 0.018, 0.025]
    
    for i, rate in enumerate(rates):
        timestamp = datetime.now() - timedelta(hours=8*(len(rates)-i))
        predictor.add_funding_rate(symbol, rate, timestamp)
    
    # Предсказание
    predicted = predictor.predict_next_rate(symbol)
    print(f"Predicted rate: {predicted:.4f}%")
    
    # Анализ возможности
    opportunity = predictor.calculate_carry_opportunity(symbol)
    print(f"Opportunity: {opportunity}")
    
    # Оптимальный тайминг
    timing = predictor.get_optimal_timing(symbol)
    print(f"Timing: {timing}")
    
    # Статистика
    stats = predictor.get_statistics()
    print(f"Statistics: {stats}")


if __name__ == '__main__':
    asyncio.run(main())
