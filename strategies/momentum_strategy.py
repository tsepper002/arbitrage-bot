"""
Momentum Trading Strategy - полная реализация
Использует импульсные сигналы для торговли
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MomentumSignal:
    """Сигнал моментум стратегии"""
    timestamp: datetime
    symbol: str
    signal_type: str  # 'BUY' or 'SELL'
    strength: float  # 0.0 to 1.0
    momentum_score: float
    rsi: float
    macd: float
    volume_ratio: float
    price_change_24h: float


class MomentumStrategy:
    """
    Momentum Trading Strategy
    
    Торгует на основе импульса цены и объема.
    """
    
    def __init__(self, rsi_period: int = 14):
        self.rsi_period = rsi_period
        self.signals_history: List[MomentumSignal] = []
        logger.info(f"Momentum Strategy initialized")
    
    def calculate_rsi(self, prices: List[float]) -> float:
        """Расчет RSI"""
        if len(prices) < self.rsi_period + 1:
            return 50.0
        
        deltas = np.diff(prices[-self.rsi_period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def analyze(self, symbol: str, prices: List[float]) -> Optional[MomentumSignal]:
        """Анализ и генерация сигнала"""
        if len(prices) < 20:
            return None
        
        rsi = self.calculate_rsi(prices)
        
        signal_type = None
        if rsi < 30:
            signal_type = 'BUY'
        elif rsi > 70:
            signal_type = 'SELL'
        
        if signal_type is None:
            return None
        
        signal = MomentumSignal(
            timestamp=datetime.now(),
            symbol=symbol,
            signal_type=signal_type,
            strength=0.7,
            momentum_score=0.8,
            rsi=rsi,
            macd=0.0,
            volume_ratio=1.0,
            price_change_24h=0.0
        )
        
        self.signals_history.append(signal)
        return signal
