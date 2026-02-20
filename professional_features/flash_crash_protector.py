"""
Flash Crash Protector
Обнаруживает аномальные движения цен и защищает капитал от крайних событий
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class FlashCrashProtector:
    """Защита от флэш-крэшей с обнаружением аномалий и circuit breakers"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Пороги для обнаружения
        self.volatility_threshold = self.config.get('volatility_threshold', 5.0)  # 5x normal
        self.price_drop_threshold = self.config.get('price_drop_threshold', 0.10)  # 10% drop
        self.volume_spike_threshold = self.config.get('volume_spike_threshold', 10.0)  # 10x normal
        
        # Окна наблюдения
        self.price_window_size = self.config.get('price_window_size', 100)
        self.volume_window_size = self.config.get('volume_window_size', 50)
        
        # Состояние
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        self.volatility_history: Dict[str, deque] = {}
        
        self.circuit_breaker_active: Dict[str, bool] = {}
        self.circuit_breaker_time: Dict[str, datetime] = {}
        self.circuit_breaker_duration = timedelta(minutes=5)
        
        self.flash_crash_detected: Dict[str, bool] = {}
        self.last_detection_time: Dict[str, datetime] = {}
        
        # Статистика
        self.stats = {
            'total_detections': 0,
            'false_positives': 0,
            'circuit_breaker_activations': 0,
            'prevented_losses': 0.0
        }
        
        logger.info("FlashCrashProtector initialized")
    
    def add_price_update(self, symbol: str, price: float, volume: float, timestamp: datetime = None):
        """Добавить обновление цены для анализа"""
        timestamp = timestamp or datetime.now()
        
        # Инициализация истории для нового символа
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.price_window_size)
            self.volume_history[symbol] = deque(maxlen=self.volume_window_size)
            self.volatility_history[symbol] = deque(maxlen=50)
            self.circuit_breaker_active[symbol] = False
            self.flash_crash_detected[symbol] = False
        
        # Добавить в историю
        self.price_history[symbol].append((timestamp, price))
        self.volume_history[symbol].append((timestamp, volume))
        
        # Вычислить волатильность
        if len(self.price_history[symbol]) >= 2:
            volatility = self._calculate_volatility(symbol)
            self.volatility_history[symbol].append((timestamp, volatility))
    
    def _calculate_volatility(self, symbol: str) -> float:
        """Вычислить текущую волатильность"""
        prices = [p for _, p in list(self.price_history[symbol])[-20:]]
        if len(prices) < 2:
            return 0.0
        
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        if not returns:
            return 0.0
        
        return statistics.stdev(returns) * 100  # В процентах
    
    def _detect_price_anomaly(self, symbol: str) -> Tuple[bool, str]:
        """Обнаружить аномалию в цене"""
        if len(self.price_history[symbol]) < 10:
            return False, ""
        
        prices = [p for _, p in list(self.price_history[symbol])]
        current_price = prices[-1]
        
        # Проверка резкого падения
        recent_high = max(prices[-10:])
        drop_pct = (recent_high - current_price) / recent_high
        
        if drop_pct > self.price_drop_threshold:
            return True, f"Price drop {drop_pct*100:.1f}% from recent high"
        
        # Проверка резкого роста (pump)
        recent_low = min(prices[-10:])
        rise_pct = (current_price - recent_low) / recent_low
        
        if rise_pct > self.price_drop_threshold * 2:  # Двойной порог для pump
            return True, f"Price pump {rise_pct*100:.1f}% from recent low"
        
        return False, ""
    
    def _detect_volatility_spike(self, symbol: str) -> Tuple[bool, str]:
        """Обнаружить всплеск волатильности"""
        if len(self.volatility_history[symbol]) < 10:
            return False, ""
        
        volatilities = [v for _, v in list(self.volatility_history[symbol])]
        current_vol = volatilities[-1]
        avg_vol = statistics.mean(volatilities[:-1])
        
        if avg_vol == 0:
            return False, ""
        
        vol_ratio = current_vol / avg_vol
        
        if vol_ratio > self.volatility_threshold:
            return True, f"Volatility spike: {vol_ratio:.1f}x normal ({current_vol:.2f}%)"
        
        return False, ""
    
    def _detect_volume_anomaly(self, symbol: str) -> Tuple[bool, str]:
        """Обнаружить аномалию в объеме"""
        if len(self.volume_history[symbol]) < 10:
            return False, ""
        
        volumes = [v for _, v in list(self.volume_history[symbol])]
        current_volume = volumes[-1]
        avg_volume = statistics.mean(volumes[:-1])
        
        if avg_volume == 0:
            return False, ""
        
        volume_ratio = current_volume / avg_volume
        
        if volume_ratio > self.volume_spike_threshold:
            return True, f"Volume spike: {volume_ratio:.1f}x normal"
        
        return False, ""
    
    def is_flash_crash(self, symbol: str) -> Tuple[bool, List[str]]:
        """Проверить, происходит ли флэш-крэш"""
        reasons = []
        
        # Проверка circuit breaker
        if self.circuit_breaker_active.get(symbol, False):
            if datetime.now() - self.circuit_breaker_time[symbol] < self.circuit_breaker_duration:
                return True, ["Circuit breaker active"]
            else:
                self.circuit_breaker_active[symbol] = False
        
        # Проверка аномалий
        price_anomaly, price_reason = self._detect_price_anomaly(symbol)
        if price_anomaly:
            reasons.append(price_reason)
        
        vol_spike, vol_reason = self._detect_volatility_spike(symbol)
        if vol_spike:
            reasons.append(vol_reason)
        
        volume_anomaly, volume_reason = self._detect_volume_anomaly(symbol)
        if volume_anomaly:
            reasons.append(volume_reason)
        
        # Флэш-крэш если 2+ аномалии одновременно
        is_crash = len(reasons) >= 2
        
        if is_crash:
            self.flash_crash_detected[symbol] = True
            self.last_detection_time[symbol] = datetime.now()
            self.stats['total_detections'] += 1
            logger.warning(f"Flash crash detected for {symbol}: {reasons}")
        
        return is_crash, reasons
    
    def activate_circuit_breaker(self, symbol: str, reason: str = "Manual activation"):
        """Активировать circuit breaker для символа"""
        self.circuit_breaker_active[symbol] = True
        self.circuit_breaker_time[symbol] = datetime.now()
        self.stats['circuit_breaker_activations'] += 1
        logger.critical(f"Circuit breaker activated for {symbol}: {reason}")
    
    def should_stop_trading(self, symbol: str) -> bool:
        """Нужно ли остановить торговлю"""
        is_crash, reasons = self.is_flash_crash(symbol)
        
        if is_crash and not self.circuit_breaker_active.get(symbol, False):
            self.activate_circuit_breaker(symbol, "; ".join(reasons))
        
        return self.circuit_breaker_active.get(symbol, False)
    
    def reset_circuit_breaker(self, symbol: str):
        """Сбросить circuit breaker вручную"""
        self.circuit_breaker_active[symbol] = False
        logger.info(f"Circuit breaker reset for {symbol}")
    
    def get_market_health(self, symbol: str) -> Dict:
        """Получить оценку здоровья рынка"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            return {
                'health_score': 1.0,
                'status': 'insufficient_data',
                'warnings': []
            }
        
        warnings = []
        health_score = 1.0
        
        # Проверка волатильности
        if len(self.volatility_history[symbol]) >= 5:
            current_vol = list(self.volatility_history[symbol])[-1][1]
            avg_vol = statistics.mean([v for _, v in list(self.volatility_history[symbol])[:-1]])
            if avg_vol > 0:
                vol_ratio = current_vol / avg_vol
                if vol_ratio > 2.0:
                    warnings.append(f"High volatility ({vol_ratio:.1f}x normal)")
                    health_score -= 0.3
        
        # Проверка тренда
        prices = [p for _, p in list(self.price_history[symbol])[-20:]]
        if len(prices) >= 2:
            trend = (prices[-1] - prices[0]) / prices[0]
            if abs(trend) > 0.05:  # 5% движение
                direction = "rising" if trend > 0 else "falling"
                warnings.append(f"Strong {direction} trend ({abs(trend)*100:.1f}%)")
                health_score -= 0.1
        
        # Проверка circuit breaker
        if self.circuit_breaker_active.get(symbol, False):
            warnings.append("Circuit breaker active")
            health_score = 0.0
        
        # Определение статуса
        if health_score >= 0.8:
            status = 'healthy'
        elif health_score >= 0.5:
            status = 'caution'
        else:
            status = 'danger'
        
        return {
            'health_score': max(0.0, health_score),
            'status': status,
            'warnings': warnings,
            'circuit_breaker': self.circuit_breaker_active.get(symbol, False)
        }
    
    def get_statistics(self) -> Dict:
        """Получить статистику работы"""
        return {
            **self.stats,
            'monitored_symbols': len(self.price_history),
            'active_circuit_breakers': sum(1 for active in self.circuit_breaker_active.values() if active)
        }


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    protector = FlashCrashProtector()
    
    # Симуляция нормальной торговли
    for i in range(50):
        price = 100 + i * 0.1
        volume = 1000
        protector.add_price_update("BTC/USDT", price, volume)
    
    # Симуляция флэш-крэша
    for i in range(10):
        price = 105 - i * 2  # Быстрое падение
        volume = 10000  # Высокий объем
        protector.add_price_update("BTC/USDT", price, volume)
    
    # Проверка
    is_crash, reasons = protector.is_flash_crash("BTC/USDT")
    print(f"Flash crash detected: {is_crash}")
    print(f"Reasons: {reasons}")
    print(f"Should stop trading: {protector.should_stop_trading('BTC/USDT')}")
    print(f"Market health: {protector.get_market_health('BTC/USDT')}")
    print(f"Statistics: {protector.get_statistics()}")
