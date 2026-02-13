"""
Mean Reversion Strategy - полная реализация
Торгует на отклонениях от средней цены
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReversionSignal:
    """Сигнал mean reversion стратегии"""
    timestamp: datetime
    symbol: str
    signal_type: str
    strength: float
    deviation: float
    bollinger_position: float
    z_score: float


class MeanReversionStrategy:
    """
    Mean Reversion Strategy
    
    Торгует на возврате к средней цене после отклонений.
    Использует Bollinger Bands и Z-score.
    """
    
    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        z_score_threshold: float = 2.0
    ):
        """
        Args:
            period: Период для moving average
            std_dev: Количество стандартных отклонений для Bollinger Bands
            z_score_threshold: Порог Z-score для сигнала
        """
        self.period = period
        self.std_dev = std_dev
        self.z_score_threshold = z_score_threshold
        self.signals_history: List[ReversionSignal] = []
        
        logger.info(f"Mean Reversion Strategy initialized (period={period}, std={std_dev})")
    
    def calculate_bollinger_bands(
        self,
        prices: List[float]
    ) -> Tuple[float, float, float]:
        """
        Расчет Bollinger Bands
        
        Returns:
            (middle_band, upper_band, lower_band)
        """
        if len(prices) < self.period:
            return 0.0, 0.0, 0.0
        
        prices_array = np.array(prices[-self.period:])
        
        middle_band = np.mean(prices_array)
        std = np.std(prices_array)
        
        upper_band = middle_band + (self.std_dev * std)
        lower_band = middle_band - (self.std_dev * std)
        
        return middle_band, upper_band, lower_band
    
    def calculate_z_score(self, prices: List[float]) -> float:
        """
        Расчет Z-score текущей цены
        
        Returns:
            Z-score значение
        """
        if len(prices) < self.period:
            return 0.0
        
        prices_array = np.array(prices[-self.period:])
        current_price = prices[-1]
        
        mean = np.mean(prices_array)
        std = np.std(prices_array)
        
        if std == 0:
            return 0.0
        
        z_score = (current_price - mean) / std
        
        return z_score
    
    def analyze(
        self,
        symbol: str,
        prices: List[float],
        current_price: float
    ) -> Optional[ReversionSignal]:
        """
        Анализ и генерация сигнала
        
        Args:
            symbol: Торговая пара
            prices: История цен
            current_price: Текущая цена
            
        Returns:
            ReversionSignal или None
        """
        if len(prices) < self.period + 5:
            logger.warning(f"Not enough data for {symbol}")
            return None
        
        # Расчет Bollinger Bands
        middle, upper, lower = self.calculate_bollinger_bands(prices)
        
        # Расчет Z-score
        z_score = self.calculate_z_score(prices)
        
        # Позиция относительно Bollinger Bands
        band_width = upper - lower
        if band_width == 0:
            bollinger_position = 0.5
        else:
            bollinger_position = (current_price - lower) / band_width
        
        # Отклонение от средней
        deviation = ((current_price - middle) / middle) * 100
        
        # Генерация сигнала
        signal_type = None
        strength = 0.0
        
        # Oversold - ожидаем reversion вверх
        if z_score < -self.z_score_threshold or bollinger_position < 0.1:
            signal_type = 'BUY'
            strength = min(abs(z_score) / 3, 1.0)
        
        # Overbought - ожидаем reversion вниз
        elif z_score > self.z_score_threshold or bollinger_position > 0.9:
            signal_type = 'SELL'
            strength = min(abs(z_score) / 3, 1.0)
        
        if signal_type is None:
            return None
        
        signal = ReversionSignal(
            timestamp=datetime.now(),
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            deviation=deviation,
            bollinger_position=bollinger_position,
            z_score=z_score
        )
        
        self.signals_history.append(signal)
        
        logger.info(
            f"Mean reversion signal: {symbol} {signal_type} "
            f"(strength={strength:.2f}, z_score={z_score:.2f}, "
            f"bb_pos={bollinger_position:.2f})"
        )
        
        return signal
    
    def get_statistics(self) -> Dict:
        """Получение статистики стратегии"""
        if not self.signals_history:
            return {
                'total_signals': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'avg_strength': 0.0,
                'avg_z_score': 0.0
            }
        
        buy_signals = [s for s in self.signals_history if s.signal_type == 'BUY']
        sell_signals = [s for s in self.signals_history if s.signal_type == 'SELL']
        
        return {
            'total_signals': len(self.signals_history),
            'buy_signals': len(buy_signals),
            'sell_signals': len(sell_signals),
            'avg_strength': np.mean([s.strength for s in self.signals_history]),
            'avg_z_score': np.mean([abs(s.z_score) for s in self.signals_history])
        }
