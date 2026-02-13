"""Index Arbitrage - Trades index vs basket of components"""
import logging
from typing import Dict, List
import asyncio

logger = logging.getLogger(__name__)

class IndexArbitrageStrategy:
    def __init__(self, exchange, index_symbol: str, components: List[tuple], 
                 threshold_pct: float = 0.005):
        self.exchange = exchange
        self.index_symbol = index_symbol
        self.components = components  # [(symbol, weight), ...]
        self.threshold = threshold_pct
        self.position = None
        self.running = False
        
    async def start(self):
        self.running = True
        logger.info(f"Starting index arbitrage for {self.index_symbol}")
        while self.running:
            try:
                await self._check_and_trade()
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Index arb error: {e}")
                await asyncio.sleep(10)
                
    def stop(self):
        self.running = False
        
    async def _check_and_trade(self):
        index_price = await self._get_price(self.index_symbol)
        basket_price = await self._calculate_basket_price()
        
        if not index_price or not basket_price:
            return
            
        spread = (index_price - basket_price) / basket_price
        logger.info(f"Index spread: {spread:.4%}")
        
        if abs(spread) > self.threshold and not self.position:
            if spread > 0:
                # Index overpriced: sell index, buy basket
                await self._sell_index_buy_basket()
                self.position = 'short_index'
            else:
                # Index underpriced: buy index, sell basket
                await self._buy_index_sell_basket()
                self.position = 'long_index'
        elif abs(spread) < self.threshold / 2 and self.position:
            await self._close_position()
            self.position = None
            
    async def _calculate_basket_price(self) -> float:
        total = 0.0
        for symbol, weight in self.components:
            price = await self._get_price(symbol)
            if price:
                total += price * weight
        return total
        
    async def _get_price(self, symbol: str) -> float:
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return (ticker['bid'] + ticker['ask']) / 2
        except:
            return None
            
    async def _sell_index_buy_basket(self):
        # Implementation
        pass
        
    async def _buy_index_sell_basket(self):
        # Implementation
        pass
        
    async def _close_position(self):
        # Implementation
        pass
        
    def get_stats(self) -> Dict:
        return {'index': self.index_symbol, 'position': self.position}
