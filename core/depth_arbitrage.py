"""
Depth Arbitrage - Order book depth analysis for large orders
Optimizes execution of large orders using orderbook depth.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OrderbookLevel:
    """Single orderbook level."""
    price: float
    volume: float
    

@dataclass
class DepthOpportunity:
    """Depth arbitrage opportunity."""
    symbol: str
    buy_exchange: str
    sell_exchange: str
    amount: float
    avg_buy_price: float
    avg_sell_price: float
    gross_profit: float
    net_profit: float
    profit_percent: float
    timestamp: datetime
    buy_levels: List[OrderbookLevel]
    sell_levels: List[OrderbookLevel]


class DepthArbitrage:
    """
    Order book depth arbitrage scanner.
    
    Features:
    - Volume-weighted average price calculation
    - Large order optimization
    - Multi-level orderbook analysis
    - Slippage estimation
    - Optimal amount calculation
    """
    
    def __init__(self, min_profit_percent: float = 0.1, fee_percent: float = 0.1):
        """
        Initialize depth arbitrage.
        
        Args:
            min_profit_percent: Minimum profit threshold
            fee_percent: Trading fee percentage (both sides)
        """
        self.min_profit_percent = min_profit_percent
        self.fee_percent = fee_percent
        
        # Orderbook cache: exchange -> symbol -> {bids: [], asks: []}
        self.orderbooks: Dict[str, Dict[str, dict]] = {}
        
        logger.info(f"DepthArbitrage initialized (min_profit={min_profit_percent}%)")
    
    async def update_orderbook(
        self,
        exchange: str,
        symbol: str,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]]
    ):
        """
        Update orderbook for an exchange.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            bids: List of (price, volume) tuples (descending)
            asks: List of (price, volume) tuples (ascending)
        """
        if exchange not in self.orderbooks:
            self.orderbooks[exchange] = {}
        
        self.orderbooks[exchange][symbol] = {
            'bids': bids,
            'asks': asks,
            'timestamp': datetime.now()
        }
    
    def _calculate_vwap(
        self,
        levels: List[Tuple[float, float]],
        amount: float,
        is_buy: bool
    ) -> Tuple[float, List[OrderbookLevel], float]:
        """
        Calculate Volume-Weighted Average Price for an amount.
        
        Args:
            levels: Orderbook levels (price, volume)
            amount: Amount to execute
            is_buy: True if buying (use asks), False if selling (use bids)
        
        Returns:
            (vwap, levels_used, total_volume_available)
        """
        total_value = 0
        total_volume = 0
        levels_used = []
        
        for price, volume in levels:
            if total_volume >= amount:
                break
            
            # How much we can take from this level
            available = min(volume, amount - total_volume)
            
            total_value += price * available
            total_volume += available
            
            levels_used.append(OrderbookLevel(price=price, volume=available))
        
        if total_volume == 0:
            return 0, [], 0
        
        vwap = total_value / total_volume
        return vwap, levels_used, total_volume
    
    async def find_opportunities(
        self,
        symbol: str,
        min_amount: float = 100,
        max_amount: float = 10000,
        amount_steps: int = 10
    ) -> List[DepthOpportunity]:
        """
        Find depth arbitrage opportunities.
        
        Args:
            symbol: Symbol to scan
            min_amount: Minimum amount to test
            max_amount: Maximum amount to test
            amount_steps: Number of amount steps to test
        
        Returns:
            List of opportunities
        """
        opportunities = []
        
        # Get all exchanges with this symbol
        exchanges_with_symbol = [
            exchange for exchange, symbols in self.orderbooks.items()
            if symbol in symbols
        ]
        
        if len(exchanges_with_symbol) < 2:
            return opportunities
        
        # Test different amounts
        amounts = [
            min_amount + (max_amount - min_amount) * i / (amount_steps - 1)
            for i in range(amount_steps)
        ]
        
        # Compare all pairs
        for i, buy_exchange in enumerate(exchanges_with_symbol):
            for sell_exchange in exchanges_with_symbol[i+1:]:
                for amount in amounts:
                    # Check both directions
                    opp = await self._check_opportunity(
                        symbol, buy_exchange, sell_exchange, amount
                    )
                    if opp and opp.profit_percent >= self.min_profit_percent:
                        opportunities.append(opp)
                    
                    opp = await self._check_opportunity(
                        symbol, sell_exchange, buy_exchange, amount
                    )
                    if opp and opp.profit_percent >= self.min_profit_percent:
                        opportunities.append(opp)
        
        # Sort by profit
        opportunities.sort(key=lambda x: x.net_profit, reverse=True)
        
        return opportunities
    
    async def _check_opportunity(
        self,
        symbol: str,
        buy_exchange: str,
        sell_exchange: str,
        amount: float
    ) -> Optional[DepthOpportunity]:
        """Check if there's an opportunity between two exchanges."""
        # Get orderbooks
        buy_ob = self.orderbooks.get(buy_exchange, {}).get(symbol)
        sell_ob = self.orderbooks.get(sell_exchange, {}).get(symbol)
        
        if not buy_ob or not sell_ob:
            return None
        
        # Calculate VWAP for buying (use asks)
        buy_vwap, buy_levels, buy_volume = self._calculate_vwap(
            buy_ob['asks'], amount, is_buy=True
        )
        
        # Calculate VWAP for selling (use bids)
        sell_vwap, sell_levels, sell_volume = self._calculate_vwap(
            sell_ob['bids'], amount, is_buy=False
        )
        
        # Check if we have enough liquidity
        if buy_volume < amount or sell_volume < amount:
            return None
        
        # Calculate profit
        buy_cost = buy_vwap * amount
        sell_proceeds = sell_vwap * amount
        
        # Subtract fees (both sides)
        buy_fee = buy_cost * (self.fee_percent / 100)
        sell_fee = sell_proceeds * (self.fee_percent / 100)
        
        gross_profit = sell_proceeds - buy_cost
        net_profit = gross_profit - buy_fee - sell_fee
        profit_percent = (net_profit / buy_cost) * 100
        
        if profit_percent <= 0:
            return None
        
        return DepthOpportunity(
            symbol=symbol,
            buy_exchange=buy_exchange,
            sell_exchange=sell_exchange,
            amount=amount,
            avg_buy_price=buy_vwap,
            avg_sell_price=sell_vwap,
            gross_profit=gross_profit,
            net_profit=net_profit,
            profit_percent=profit_percent,
            timestamp=datetime.now(),
            buy_levels=buy_levels,
            sell_levels=sell_levels
        )
    
    async def execute_opportunity(self, opportunity: DepthOpportunity) -> dict:
        """
        Execute depth arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to execute
        
        Returns:
            Execution result
        """
        logger.info(
            f"Executing depth arbitrage: {opportunity.symbol}, "
            f"amount={opportunity.amount}, "
            f"profit={opportunity.profit_percent:.2f}%"
        )
        
        try:
            # Execute buy orders
            buy_result = await self._execute_orders(
                opportunity.buy_exchange,
                opportunity.symbol,
                'buy',
                opportunity.buy_levels
            )
            
            # Execute sell orders
            sell_result = await self._execute_orders(
                opportunity.sell_exchange,
                opportunity.symbol,
                'sell',
                opportunity.sell_levels
            )
            
            # Calculate actual profit
            actual_buy_cost = sum(
                level['price'] * level['filled']
                for level in buy_result['levels']
            )
            
            actual_sell_proceeds = sum(
                level['price'] * level['filled']
                for level in sell_result['levels']
            )
            
            actual_profit = actual_sell_proceeds - actual_buy_cost
            actual_profit_percent = (actual_profit / actual_buy_cost) * 100
            
            logger.info(f"Depth arbitrage completed: profit = ${actual_profit:.2f} ({actual_profit_percent:.2f}%)")
            
            return {
                'success': True,
                'buy_result': buy_result,
                'sell_result': sell_result,
                'actual_profit': actual_profit,
                'actual_profit_percent': actual_profit_percent,
                'expected_profit': opportunity.net_profit,
                'slippage': actual_profit - opportunity.net_profit
            }
        
        except Exception as e:
            logger.error(f"Depth arbitrage failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _execute_orders(
        self,
        exchange: str,
        symbol: str,
        side: str,
        levels: List[OrderbookLevel]
    ) -> dict:
        """Execute orders at multiple price levels."""
        # Placeholder - integrate with actual exchange
        logger.info(f"Executing {side} orders on {exchange} for {symbol}")
        
        executed_levels = []
        for level in levels:
            executed_levels.append({
                'price': level.price,
                'volume': level.volume,
                'filled': level.volume  # Assume 100% fill for now
            })
        
        return {
            'exchange': exchange,
            'symbol': symbol,
            'side': side,
            'levels': executed_levels
        }
    
    async def estimate_slippage(
        self,
        symbol: str,
        exchange: str,
        amount: float,
        side: str
    ) -> dict:
        """
        Estimate slippage for a large order.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            amount: Order amount
            side: 'buy' or 'sell'
        
        Returns:
            Slippage estimation
        """
        ob = self.orderbooks.get(exchange, {}).get(symbol)
        
        if not ob:
            return {'error': 'Orderbook not available'}
        
        levels = ob['asks'] if side == 'buy' else ob['bids']
        
        # Get best price (first level)
        if not levels:
            return {'error': 'Empty orderbook'}
        
        best_price = levels[0][0]
        
        # Calculate VWAP
        vwap, levels_used, available_volume = self._calculate_vwap(
            levels, amount, is_buy=(side == 'buy')
        )
        
        if available_volume < amount:
            return {
                'error': 'Insufficient liquidity',
                'requested': amount,
                'available': available_volume
            }
        
        # Calculate slippage
        slippage_percent = ((vwap - best_price) / best_price) * 100
        
        if side == 'sell':
            slippage_percent = -slippage_percent  # Selling at lower price is negative slippage
        
        return {
            'best_price': best_price,
            'vwap': vwap,
            'slippage_percent': slippage_percent,
            'levels_used': len(levels_used),
            'available_volume': available_volume
        }
    
    async def get_stats(self) -> dict:
        """Get depth arbitrage statistics."""
        total_symbols = set()
        for exchange_symbols in self.orderbooks.values():
            total_symbols.update(exchange_symbols.keys())
        
        return {
            'exchanges_monitored': len(self.orderbooks),
            'symbols_monitored': len(total_symbols),
            'min_profit_threshold': self.min_profit_percent,
            'fee_percent': self.fee_percent
        }


# Global instance
_depth_arbitrage: Optional[DepthArbitrage] = None


def get_depth_arbitrage(min_profit_percent: float = 0.1) -> DepthArbitrage:
    """
    Get depth arbitrage instance.
    
    Args:
        min_profit_percent: Minimum profit threshold
    
    Returns:
        DepthArbitrage instance
    """
    global _depth_arbitrage
    
    if _depth_arbitrage is None:
        _depth_arbitrage = DepthArbitrage(min_profit_percent=min_profit_percent)
    
    return _depth_arbitrage


# Usage example
"""
from core.depth_arbitrage import get_depth_arbitrage

depth_arb = get_depth_arbitrage()

# Update orderbooks
await depth_arb.update_orderbook(
    'Bybit',
    'BTC/USDT',
    bids=[(50000, 1.5), (49990, 2.0), (49980, 1.0)],
    asks=[(50010, 1.0), (50020, 2.0), (50030, 3.0)]
)

await depth_arb.update_orderbook(
    'KuCoin',
    'BTC/USDT',
    bids=[(50050, 2.0), (50040, 1.5), (50030, 2.5)],
    asks=[(50060, 1.5), (50070, 2.0), (50080, 2.5)]
)

# Find opportunities
opportunities = await depth_arb.find_opportunities('BTC/USDT', min_amount=0.1, max_amount=5.0)

for opp in opportunities:
    print(f"Buy {opp.amount} on {opp.buy_exchange} at ${opp.avg_buy_price:.2f}")
    print(f"Sell {opp.amount} on {opp.sell_exchange} at ${opp.avg_sell_price:.2f}")
    print(f"Profit: ${opp.net_profit:.2f} ({opp.profit_percent:.2f}%)")

# Execute best opportunity
if opportunities:
    result = await depth_arb.execute_opportunity(opportunities[0])
    print(f"Result: {result}")

# Estimate slippage
slippage = await depth_arb.estimate_slippage('BTC/USDT', 'Bybit', 2.0, 'buy')
print(f"Estimated slippage: {slippage['slippage_percent']:.2f}%")
"""
