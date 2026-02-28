"""Pairs Trading - Correlation-based trading"""
import logging
from typing import Dict
import asyncio
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)

class PairsTradingStrategy:
    def __init__(self, exchange, pair1: str, pair2: str, lookback: int = 60,
                 entry_z: float = 2.0, exit_z: float = 0.5):
        self.exchange = exchange
        self.pair1 = pair1
        self.pair2 = pair2
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.ratios = deque(maxlen=lookback)
        self.position = None
        self.running = False
        
    async def start(self):
        self.running = True
        logger.info(f"Starting pairs trading: {self.pair1}/{self.pair2}")
        while self.running:
            try:
                await self._analyze_and_trade()
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Pairs error: {e}")
                await asyncio.sleep(60)
                
    def stop(self):
        self.running = False
        
    async def _analyze_and_trade(self):
        price1 = await self._get_price(self.pair1)
        price2 = await self._get_price(self.pair2)
        if not price1 or not price2:
            return
            
        ratio = price1 / price2
        self.ratios.append(ratio)
        
        if len(self.ratios) < self.lookback:
            return
            
        mean = np.mean(self.ratios)
        std = np.std(self.ratios)
        z_score = (ratio - mean) / std if std > 0 else 0
        
        logger.info(f"Z-score: {z_score:.2f}")
        
        if not self.position:
            if z_score > self.entry_z:
                self.position = 'short_pair1_long_pair2'
                logger.info("Entered short pair1, long pair2")
            elif z_score < -self.entry_z:
                self.position = 'long_pair1_short_pair2'
                logger.info("Entered long pair1, short pair2")
        else:
            if abs(z_score) < self.exit_z:
                logger.info("Exiting position")
                self.position = None
                
    async def _get_price(self, symbol: str) -> float:
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return (ticker['bid'] + ticker['ask']) / 2
        except (KeyError, TypeError, ValueError, Exception):
            return None
            
    def get_stats(self) -> Dict:
        return {'pair1': self.pair1, 'pair2': self.pair2, 'position': self.position}
