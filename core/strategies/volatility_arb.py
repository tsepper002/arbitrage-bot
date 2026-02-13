"""
Volatility Arbitrage Strategy
Trades based on implied vs realized volatility differences
"""

import logging
from typing import Dict, Optional
import asyncio
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)


class VolatilityArbitrageStrategy:
    """
    Volatility Arbitrage Strategy
    
    Exploits differences between implied volatility (from options)
    and realized volatility (from price movements).
    """
    
    def __init__(
        self,
        exchange_client,
        symbol: str,
        lookback_period: int = 30,
        vol_threshold: float = 0.2,  # 20% difference
        position_size_usdt: float = 500.0
    ):
        self.exchange = exchange_client
        self.symbol = symbol
        self.lookback_period = lookback_period
        self.vol_threshold = vol_threshold
        self.position_size = position_size_usdt
        
        self.price_history = deque(maxlen=lookback_period)
        self.position: Optional[str] = None
        self.running = False
        
    async def start(self):
        """Start strategy"""
        self.running = True
        logger.info(f"Starting volatility arbitrage for {self.symbol}")
        
        while self.running:
            try:
                await self._analyze_and_trade()
                await asyncio.sleep(3600)  # Check hourly
            except Exception as e:
                logger.error(f"Error in volatility arbitrage: {e}")
                await asyncio.sleep(600)
    
    def stop(self):
        """Stop strategy"""
        self.running = False
    
    async def _analyze_and_trade(self):
        """Analyze volatility and trade"""
        # Get current price
        price = await self._get_price()
        if not price:
            return
        
        self.price_history.append(price)
        
        if len(self.price_history) < self.lookback_period:
            logger.info(f"Building history: {len(self.price_history)}/{self.lookback_period}")
            return
        
        # Calculate realized volatility
        realized_vol = self._calculate_realized_volatility()
        
        # Get implied volatility (from options if available)
        implied_vol = await self._get_implied_volatility()
        
        if implied_vol is None:
            logger.warning("Cannot get implied volatility")
            return
        
        vol_diff = (implied_vol - realized_vol) / realized_vol
        
        logger.info(f"Realized vol: {realized_vol:.2%}, Implied vol: {implied_vol:.2%}, Diff: {vol_diff:.2%}")
        
        if self.position is None:
            await self._check_entry(vol_diff, realized_vol, implied_vol)
        else:
            await self._check_exit(vol_diff)
    
    def _calculate_realized_volatility(self) -> float:
        """Calculate historical/realized volatility"""
        prices = np.array(self.price_history)
        returns = np.diff(np.log(prices))
        
        # Annualized volatility (assuming hourly data)
        volatility = np.std(returns) * np.sqrt(24 * 365)
        
        return volatility
    
    async def _get_implied_volatility(self) -> Optional[float]:
        """Get implied volatility from options"""
        try:
            # This would require options data
            # For now, simulate or use ATM option IV
            # In production, fetch from options exchange
            
            # Placeholder: return a value for testing
            # In real implementation, fetch actual IV from options
            return 0.5  # 50% IV placeholder
            
        except Exception as e:
            logger.error(f"Failed to get implied volatility: {e}")
            return None
    
    async def _check_entry(self, vol_diff: float, realized_vol: float, implied_vol: float):
        """Check for entry signals"""
        if vol_diff > self.vol_threshold:
            # Implied > Realized: volatility is overpriced
            # -> Sell volatility (sell straddle/strangle)
            await self._sell_volatility()
            self.position = 'short_vol'
            logger.info(f"Entered SHORT volatility (IV overpriced by {vol_diff:.2%})")
            
        elif vol_diff < -self.vol_threshold:
            # Realized > Implied: volatility is underpriced
            # -> Buy volatility (buy straddle/strangle)
            await self._buy_volatility()
            self.position = 'long_vol'
            logger.info(f"Entered LONG volatility (IV underpriced by {vol_diff:.2%})")
    
    async def _check_exit(self, vol_diff: float):
        """Check for exit signals"""
        # Exit when vol_diff normalizes
        if abs(vol_diff) < self.vol_threshold / 2:
            await self._close_position()
            logger.info(f"Closed volatility position")
            self.position = None
    
    async def _buy_volatility(self):
        """Buy volatility (long gamma)"""
        try:
            # In practice: buy ATM straddle (call + put)
            # For spot market: can use delta-hedged long options
            
            price = await self._get_price()
            amount = self.position_size / price
            
            # Simplified: just buy underlying (should be options in reality)
            await self.exchange.create_market_buy_order(self.symbol, amount)
            
            logger.info("Bought volatility exposure")
            
        except Exception as e:
            logger.error(f"Failed to buy volatility: {e}")
    
    async def _sell_volatility(self):
        """Sell volatility (short gamma)"""
        try:
            # In practice: sell ATM straddle (call + put)
            # For spot market: can use delta-hedged short options
            
            price = await self._get_price()
            amount = self.position_size / price
            
            # Simplified: just sell underlying (should be options in reality)
            await self.exchange.create_market_sell_order(self.symbol, amount)
            
            logger.info("Sold volatility exposure")
            
        except Exception as e:
            logger.error(f"Failed to sell volatility: {e}")
    
    async def _close_position(self):
        """Close volatility position"""
        try:
            price = await self._get_price()
            amount = self.position_size / price
            
            if self.position == 'long_vol':
                await self.exchange.create_market_sell_order(self.symbol, amount)
            else:
                await self.exchange.create_market_buy_order(self.symbol, amount)
                
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
    
    async def _get_price(self) -> Optional[float]:
        """Get current price"""
        try:
            ticker = await self.exchange.fetch_ticker(self.symbol)
            return (ticker['bid'] + ticker['ask']) / 2
        except Exception as e:
            logger.error(f"Failed to get price: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Get strategy statistics"""
        realized_vol = self._calculate_realized_volatility() if len(self.price_history) >= 2 else 0.0
        
        return {
            'symbol': self.symbol,
            'position': self.position,
            'realized_volatility': realized_vol,
            'price_history_len': len(self.price_history)
        }
