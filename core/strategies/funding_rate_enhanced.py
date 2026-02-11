"""
Enhanced Funding Rate Arbitrage Strategy
Captures profits from perpetual funding rates vs spot holdings
"""

import logging
from typing import Dict, Optional
import asyncio

logger = logging.getLogger(__name__)


class FundingRateEnhancedStrategy:
    """
    Enhanced Funding Rate Arbitrage
    
    Exploits the difference between perpetual funding rates and spot holdings.
    Long perpetual + short spot when funding is negative (get paid).
    Short perpetual + long spot when funding is positive (avoid paying).
    """
    
    def __init__(
        self,
        exchange_client,
        symbol: str,
        min_funding_rate: float = 0.0001,  # 0.01% minimum
        position_size_usdt: float = 1000.0,
        hold_duration_hours: int = 8
    ):
        self.exchange = exchange_client
        self.symbol = symbol
        self.min_funding_rate = min_funding_rate
        self.position_size = position_size_usdt
        self.hold_duration = hold_duration_hours
        
        self.position: Optional[str] = None  # 'long' or 'short'
        self.entry_time = None
        self.accumulated_funding = 0.0
        self.running = False
        
    async def start(self):
        """Start strategy"""
        self.running = True
        logger.info(f"Starting funding rate arbitrage for {self.symbol}")
        
        while self.running:
            try:
                await self._check_and_trade()
                await asyncio.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Error in funding rate arbitrage: {e}")
                await asyncio.sleep(60)
    
    def stop(self):
        """Stop strategy"""
        self.running = False
    
    async def _check_and_trade(self):
        """Check funding rate and execute trades"""
        # Get funding rate
        funding_rate = await self._get_funding_rate()
        
        if funding_rate is None:
            return
        
        logger.info(f"Current funding rate: {funding_rate*100:.4f}%")
        
        if self.position is None:
            await self._check_entry(funding_rate)
        else:
            await self._check_exit(funding_rate)
    
    async def _check_entry(self, funding_rate: float):
        """Check for entry opportunities"""
        # Enter if funding rate is significant
        if abs(funding_rate) > self.min_funding_rate:
            if funding_rate > 0:
                # Positive funding: shorts pay longs
                # -> Go long perpetual, short spot
                await self._enter_long_position()
                self.position = 'long'
                logger.info(f"Entered LONG at funding rate {funding_rate*100:.4f}%")
                
            else:
                # Negative funding: longs pay shorts
                # -> Go short perpetual, long spot
                await self._enter_short_position()
                self.position = 'short'
                logger.info(f"Entered SHORT at funding rate {funding_rate*100:.4f}%")
            
            self.entry_time = asyncio.get_event_loop().time()
    
    async def _check_exit(self, funding_rate: float):
        """Check if should exit position"""
        if self.entry_time is None:
            return
        
        elapsed_hours = (asyncio.get_event_loop().time() - self.entry_time) / 3600
        
        # Exit conditions:
        # 1. Held for target duration
        # 2. Funding rate reversed significantly
        should_exit = False
        
        if elapsed_hours >= self.hold_duration:
            should_exit = True
            logger.info(f"Exiting: held for {elapsed_hours:.1f} hours")
        
        elif self.position == 'long' and funding_rate < -self.min_funding_rate:
            should_exit = True
            logger.info("Exiting: funding rate turned negative")
            
        elif self.position == 'short' and funding_rate > self.min_funding_rate:
            should_exit = True
            logger.info("Exiting: funding rate turned positive")
        
        if should_exit:
            await self._close_position()
            logger.info(f"Closed position. Accumulated funding: {self.accumulated_funding:.4f} USDT")
            self.position = None
            self.entry_time = None
    
    async def _enter_long_position(self):
        """Enter long perpetual + short spot"""
        try:
            # Get current price
            price = await self._get_price()
            amount = self.position_size / price
            
            # Buy perpetual (with leverage if available)
            await self.exchange.create_market_buy_order(
                f"{self.symbol}/USDT:USDT",  # Perpetual
                amount
            )
            
            # Short spot (or just hold USDT)
            # In practice, we'd sell spot or use futures
            
        except Exception as e:
            logger.error(f"Failed to enter long position: {e}")
    
    async def _enter_short_position(self):
        """Enter short perpetual + long spot"""
        try:
            price = await self._get_price()
            amount = self.position_size / price
            
            # Sell perpetual (with leverage if available)
            await self.exchange.create_market_sell_order(
                f"{self.symbol}/USDT:USDT",  # Perpetual
                amount
            )
            
            # Buy spot
            await self.exchange.create_market_buy_order(
                f"{self.symbol}/USDT",  # Spot
                amount
            )
            
        except Exception as e:
            logger.error(f"Failed to enter short position: {e}")
    
    async def _close_position(self):
        """Close current position"""
        try:
            price = await self._get_price()
            amount = self.position_size / price
            
            if self.position == 'long':
                # Close long: sell perpetual
                await self.exchange.create_market_sell_order(
                    f"{self.symbol}/USDT:USDT",
                    amount
                )
            else:
                # Close short: buy perpetual, sell spot
                await self.exchange.create_market_buy_order(
                    f"{self.symbol}/USDT:USDT",
                    amount
                )
                await self.exchange.create_market_sell_order(
                    f"{self.symbol}/USDT",
                    amount
                )
                
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
    
    async def _get_funding_rate(self) -> Optional[float]:
        """Get current funding rate"""
        try:
            # This is exchange-specific
            # For Bybit/Binance etc, there's a funding rate API
            funding_info = await self.exchange.fetch_funding_rate(self.symbol)
            return funding_info.get('fundingRate', 0.0)
        except Exception as e:
            logger.error(f"Failed to get funding rate: {e}")
            return None
    
    async def _get_price(self) -> float:
        """Get current price"""
        ticker = await self.exchange.fetch_ticker(self.symbol)
        return (ticker['bid'] + ticker['ask']) / 2
    
    def get_stats(self) -> Dict:
        """Get strategy statistics"""
        return {
            'symbol': self.symbol,
            'position': self.position,
            'accumulated_funding': self.accumulated_funding,
            'entry_time': self.entry_time
        }
