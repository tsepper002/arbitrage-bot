"""
DCA (Dollar Cost Averaging) Strategy - Accumulates positions over time
"""
import logging
from typing import Dict
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class DCAStrategy:
    def __init__(self, exchange, symbol: str, amount_per_buy: float = 50.0,
                 interval_hours: int = 24, max_position_usdt: float = 1000.0):
        self.exchange = exchange
        self.symbol = symbol
        self.amount_per_buy = amount_per_buy
        self.interval_hours = interval_hours
        self.max_position = max_position_usdt
        self.total_invested = 0.0
        self.total_amount = 0.0
        self.running = False
        
    async def start(self):
        self.running = True
        logger.info(f"Starting DCA for {self.symbol}")
        while self.running:
            try:
                await self._execute_buy()
                await asyncio.sleep(self.interval_hours * 3600)
            except Exception as e:
                logger.error(f"DCA error: {e}")
                await asyncio.sleep(3600)
    
    def stop(self):
        self.running = False
        
    async def _execute_buy(self):
        if self.total_invested >= self.max_position:
            logger.info("Max position reached, skipping buy")
            return
            
        try:
            ticker = await self.exchange.fetch_ticker(self.symbol)
            price = (ticker['bid'] + ticker['ask']) / 2
            if price <= 0:
                logger.warning(f"DCA: invalid price {price} for {self.symbol}")
                return
            amount = min(self.amount_per_buy, self.max_position - self.total_invested) / price
            
            order = await self.exchange.create_market_buy_order(self.symbol, amount)
            self.total_invested += self.amount_per_buy
            self.total_amount += amount
            
            avg_price = self.total_invested / self.total_amount if self.total_amount > 0 else 0
            logger.info(f"DCA buy: {amount:.6f} @ {price:.2f}, Avg: {avg_price:.2f}")
        except Exception as e:
            logger.error(f"Failed to execute DCA buy: {e}")
            
    def get_stats(self) -> Dict:
        avg_price = self.total_invested / self.total_amount if self.total_amount > 0 else 0
        return {
            'symbol': self.symbol,
            'total_invested': self.total_invested,
            'total_amount': self.total_amount,
            'average_price': avg_price
        }
