"""
Grid Trading Strategy - Places buy/sell orders at regular intervals
"""
import logging
from typing import Dict, List
import asyncio

logger = logging.getLogger(__name__)

class GridTradingStrategy:
    def __init__(self, exchange, symbol: str, grid_levels: int = 10, 
                 price_range_pct: float = 0.1, capital_per_level: float = 50.0):
        self.exchange = exchange
        self.symbol = symbol
        self.grid_levels = grid_levels
        self.price_range_pct = price_range_pct
        self.capital_per_level = capital_per_level
        self.grid_orders: Dict[float, str] = {}
        self.running = False
        
    async def start(self):
        self.running = True
        logger.info(f"Starting grid trading for {self.symbol}")
        await self._setup_grid()
        while self.running:
            try:
                await self._monitor_and_rebalance()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Grid error: {e}")
                await asyncio.sleep(10)
    
    def stop(self):
        self.running = False
        
    async def _setup_grid(self):
        ticker = await self.exchange.fetch_ticker(self.symbol)
        mid_price = (ticker['bid'] + ticker['ask']) / 2
        
        lower_bound = mid_price * (1 - self.price_range_pct / 2)
        upper_bound = mid_price * (1 + self.price_range_pct / 2)
        price_step = (upper_bound - lower_bound) / self.grid_levels
        
        for i in range(self.grid_levels + 1):
            price = lower_bound + i * price_step
            if price < mid_price:
                # Buy orders below
                await self._place_buy(price)
            elif price > mid_price:
                # Sell orders above
                await self._place_sell(price)
                
    async def _place_buy(self, price: float):
        try:
            amount = self.capital_per_level / price
            order = await self.exchange.create_limit_buy_order(self.symbol, amount, price)
            self.grid_orders[price] = order['id']
        except Exception as e:
            logger.error(f"Failed to place buy at {price}: {e}")
            
    async def _place_sell(self, price: float):
        try:
            amount = self.capital_per_level / price
            order = await self.exchange.create_limit_sell_order(self.symbol, amount, price)
            self.grid_orders[price] = order['id']
        except Exception as e:
            logger.error(f"Failed to place sell at {price}: {e}")
            
    async def _monitor_and_rebalance(self):
        # Check filled orders and replace them
        for price, order_id in list(self.grid_orders.items()):
            try:
                order = await self.exchange.fetch_order(order_id, self.symbol)
                if order['status'] == 'closed':
                    del self.grid_orders[price]
                    # Place opposite order
                    ticker = await self.exchange.fetch_ticker(self.symbol)
                    mid = (ticker['bid'] + ticker['ask']) / 2
                    if price < mid:
                        await self._place_sell(price + (self.price_range_pct * mid / self.grid_levels))
                    else:
                        await self._place_buy(price - (self.price_range_pct * mid / self.grid_levels))
            except Exception:
                pass
                
    def get_stats(self) -> Dict:
        return {'symbol': self.symbol, 'active_orders': len(self.grid_orders)}
