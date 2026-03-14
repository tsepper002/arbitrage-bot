"""
Market Making Strategy
Provides liquidity to the market by placing both buy and sell orders
"""

import logging
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
import asyncio

logger = logging.getLogger(__name__)


class MarketMakingStrategy:
    """
    Market Making Strategy Implementation
    
    Places orders on both sides of the order book to capture the spread.
    Manages inventory risk and adjusts prices dynamically.
    """
    
    def __init__(
        self,
        exchange_client,
        symbol: str,
        spread_pct: float = 0.002,  # 0.2% default spread
        order_size_usdt: float = 100.0,
        max_inventory_usdt: float = 500.0,
        refresh_interval_sec: int = 10
    ):
        self.exchange = exchange_client
        self.symbol = symbol
        self.spread_pct = spread_pct
        self.order_size_usdt = order_size_usdt
        self.max_inventory_usdt = max_inventory_usdt
        self.refresh_interval = refresh_interval_sec
        
        self.active_orders: Dict[str, dict] = {}
        self.inventory = 0.0
        self.running = False
        
    async def start(self):
        """Start market making"""
        self.running = True
        logger.info(f"Starting market making for {self.symbol}")
        
        while self.running:
            try:
                await self._update_quotes()
                await asyncio.sleep(self.refresh_interval)
            except Exception as e:
                logger.error(f"Error in market making loop: {e}")
                await asyncio.sleep(5)
    
    def stop(self):
        """Stop market making"""
        self.running = False
        logger.info(f"Stopping market making for {self.symbol}")
    
    async def _update_quotes(self):
        """Update buy and sell quotes"""
        # Cancel existing orders
        await self._cancel_all_orders()
        
        # Get current market price
        ticker = await self.exchange.fetch_ticker(self.symbol)
        mid_price = (ticker['bid'] + ticker['ask']) / 2
        if mid_price <= 0:
            logger.warning(f"MM: invalid mid_price for {self.symbol}")
            return
        
        # Calculate inventory skew
        inventory_skew = self._calculate_inventory_skew()
        
        # Adjust spread based on inventory
        adjusted_spread = self.spread_pct * (1 + abs(inventory_skew) * 0.5)
        
        # Calculate bid/ask prices
        bid_price = mid_price * (1 - adjusted_spread / 2) * (1 - inventory_skew * 0.001)
        ask_price = mid_price * (1 + adjusted_spread / 2) * (1 + inventory_skew * 0.001)
        
        # Place orders if within inventory limits
        if self.inventory < self.max_inventory_usdt:
            await self._place_bid(bid_price)
        
        if self.inventory > -self.max_inventory_usdt:
            await self._place_ask(ask_price)
    
    def _calculate_inventory_skew(self) -> float:
        """Calculate inventory skew (-1 to 1)"""
        if self.max_inventory_usdt == 0:
            return 0.0
        return self.inventory / self.max_inventory_usdt
    
    async def _place_bid(self, price: float):
        """Place buy order"""
        try:
            amount = self.order_size_usdt / price
            order = await self.exchange.create_limit_buy_order(
                self.symbol,
                amount,
                price
            )
            self.active_orders[order['id']] = {'side': 'buy', 'order': order}
            logger.info(f"Placed bid at {price} for {amount}")
        except Exception as e:
            logger.error(f"Failed to place bid: {e}")
    
    async def _place_ask(self, price: float):
        """Place sell order"""
        try:
            amount = self.order_size_usdt / price
            order = await self.exchange.create_limit_sell_order(
                self.symbol,
                amount,
                price
            )
            self.active_orders[order['id']] = {'side': 'sell', 'order': order}
            logger.info(f"Placed ask at {price} for {amount}")
        except Exception as e:
            logger.error(f"Failed to place ask: {e}")
    
    async def _cancel_all_orders(self):
        """Cancel all active orders"""
        for order_id, order_info in list(self.active_orders.items()):
            try:
                await self.exchange.cancel_order(order_id, self.symbol)
                del self.active_orders[order_id]
            except Exception as e:
                logger.error(f"Failed to cancel order {order_id}: {e}")
    
    async def update_inventory(self, trades: List[dict]):
        """Update inventory based on filled trades"""
        for trade in trades:
            if trade['side'] == 'buy':
                self.inventory += trade['amount'] * trade['price']
            else:
                self.inventory -= trade['amount'] * trade['price']
        
        logger.info(f"Current inventory: {self.inventory} USDT")
    
    def get_stats(self) -> Dict:
        """Get strategy statistics"""
        return {
            'symbol': self.symbol,
            'active_orders': len(self.active_orders),
            'inventory_usdt': self.inventory,
            'inventory_skew': self._calculate_inventory_skew(),
            'running': self.running
        }
