"""
Cross-Chain Arbitrage - Multi-blockchain arbitrage opportunities
Finds price discrepancies across different blockchain networks.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Bridge:
    """Represents a cross-chain bridge."""
    name: str
    source_chain: str
    dest_chain: str
    fee_percent: float
    min_amount: float
    max_amount: float
    avg_time_minutes: int


@dataclass
class CrossChainOpportunity:
    """Cross-chain arbitrage opportunity."""
    symbol: str
    source_chain: str
    source_exchange: str
    source_price: float
    dest_chain: str
    dest_exchange: str
    dest_price: float
    bridge: Bridge
    gross_profit_percent: float
    net_profit_percent: float
    estimated_gas_cost: float
    timestamp: datetime


class CrossChainArbitrage:
    """
    Cross-chain arbitrage scanner and executor.
    
    Features:
    - Multi-blockchain price monitoring
    - Bridge integration (Polygon, Arbitrum, Optimism, etc.)
    - Gas cost optimization
    - Automatic opportunity detection
    - Risk assessment
    """
    
    def __init__(self, bridges: List[Bridge], min_profit_percent: float = 0.5):
        """
        Initialize cross-chain arbitrage.
        
        Args:
            bridges: List of available bridges
            min_profit_percent: Minimum net profit threshold
        """
        self.bridges = {(b.source_chain, b.dest_chain): b for b in bridges}
        self.min_profit_percent = min_profit_percent
        
        # Price caches per chain
        self.prices: Dict[str, Dict[str, float]] = {}  # chain -> {symbol: price}
        
        logger.info(f"CrossChainArbitrage initialized with {len(bridges)} bridges")
    
    async def update_price(self, chain: str, exchange: str, symbol: str, price: float):
        """
        Update price for a symbol on a specific chain.
        
        Args:
            chain: Blockchain name (e.g., 'ethereum', 'polygon')
            exchange: Exchange name
            symbol: Trading symbol
            price: Current price
        """
        key = f"{chain}:{exchange}"
        
        if key not in self.prices:
            self.prices[key] = {}
        
        self.prices[key][symbol] = price
    
    async def find_opportunities(self, symbol: str) -> List[CrossChainOpportunity]:
        """
        Find cross-chain arbitrage opportunities for a symbol.
        
        Args:
            symbol: Symbol to scan
        
        Returns:
            List of opportunities
        """
        opportunities = []
        
        # Get all price points for this symbol across chains
        price_points = []
        for key, prices in self.prices.items():
            if symbol in prices:
                chain, exchange = key.split(':')
                price_points.append((chain, exchange, prices[symbol]))
        
        if len(price_points) < 2:
            return opportunities
        
        # Compare all pairs
        for i, (source_chain, source_exchange, source_price) in enumerate(price_points):
            for dest_chain, dest_exchange, dest_price in price_points[i+1:]:
                # Check both directions
                await self._check_opportunity(
                    symbol,
                    source_chain, source_exchange, source_price,
                    dest_chain, dest_exchange, dest_price,
                    opportunities
                )
                
                await self._check_opportunity(
                    symbol,
                    dest_chain, dest_exchange, dest_price,
                    source_chain, source_exchange, source_price,
                    opportunities
                )
        
        # Filter by minimum profit
        opportunities = [
            opp for opp in opportunities
            if opp.net_profit_percent >= self.min_profit_percent
        ]
        
        # Sort by net profit
        opportunities.sort(key=lambda x: x.net_profit_percent, reverse=True)
        
        return opportunities
    
    async def _check_opportunity(
        self,
        symbol: str,
        source_chain: str, source_exchange: str, source_price: float,
        dest_chain: str, dest_exchange: str, dest_price: float,
        opportunities: List[CrossChainOpportunity]
    ):
        """Check if there's an opportunity between two chains."""
        # Skip same chain
        if source_chain == dest_chain:
            return
        
        # Find bridge
        bridge_key = (source_chain, dest_chain)
        if bridge_key not in self.bridges:
            return
        
        bridge = self.bridges[bridge_key]
        
        # Calculate profit
        if source_price <= 0:
            return
        gross_profit_percent = ((dest_price - source_price) / source_price) * 100
        
        # Estimate costs
        bridge_fee_percent = bridge.fee_percent
        gas_cost_percent = await self._estimate_gas_cost_percent(source_chain, dest_chain)
        
        net_profit_percent = gross_profit_percent - bridge_fee_percent - gas_cost_percent
        
        # Only create opportunity if profitable
        if net_profit_percent > 0:
            estimated_gas_cost = source_price * (gas_cost_percent / 100)
            
            opportunity = CrossChainOpportunity(
                symbol=symbol,
                source_chain=source_chain,
                source_exchange=source_exchange,
                source_price=source_price,
                dest_chain=dest_chain,
                dest_exchange=dest_exchange,
                dest_price=dest_price,
                bridge=bridge,
                gross_profit_percent=gross_profit_percent,
                net_profit_percent=net_profit_percent,
                estimated_gas_cost=estimated_gas_cost,
                timestamp=datetime.now()
            )
            
            opportunities.append(opportunity)
    
    async def _estimate_gas_cost_percent(self, source_chain: str, dest_chain: str) -> float:
        """
        Estimate gas cost as percentage of trade value.
        
        Args:
            source_chain: Source blockchain
            dest_chain: Destination blockchain
        
        Returns:
            Estimated gas cost percentage
        """
        # Simplified gas cost estimation
        gas_costs = {
            'ethereum': 0.3,  # 0.3% typical gas cost on Ethereum
            'polygon': 0.01,  # Very low on Polygon
            'arbitrum': 0.05,  # Low on Arbitrum
            'optimism': 0.05,  # Low on Optimism
            'bsc': 0.02,  # Low on BSC
        }
        
        source_cost = gas_costs.get(source_chain.lower(), 0.1)
        dest_cost = gas_costs.get(dest_chain.lower(), 0.1)
        
        return source_cost + dest_cost
    
    async def execute_arbitrage(self, opportunity: CrossChainOpportunity, amount: float) -> dict:
        """
        Execute cross-chain arbitrage.
        
        Args:
            opportunity: Opportunity to execute
            amount: Amount to trade
        
        Returns:
            Execution result
        """
        logger.info(
            f"Executing cross-chain arbitrage: {opportunity.symbol} "
            f"{opportunity.source_chain} -> {opportunity.dest_chain}, "
            f"profit: {opportunity.net_profit_percent:.2f}%"
        )
        
        # Check bridge limits
        if amount < opportunity.bridge.min_amount:
            raise ValueError(f"Amount {amount} below bridge minimum {opportunity.bridge.min_amount}")
        
        if amount > opportunity.bridge.max_amount:
            raise ValueError(f"Amount {amount} above bridge maximum {opportunity.bridge.max_amount}")
        
        try:
            # Step 1: Buy on source chain
            buy_result = await self._buy_on_chain(
                opportunity.source_chain,
                opportunity.source_exchange,
                opportunity.symbol,
                amount,
                opportunity.source_price
            )
            
            # Step 2: Bridge to destination chain
            bridge_result = await self._bridge_tokens(
                opportunity.bridge,
                opportunity.symbol,
                amount
            )
            
            # Step 3: Sell on destination chain
            sell_result = await self._sell_on_chain(
                opportunity.dest_chain,
                opportunity.dest_exchange,
                opportunity.symbol,
                amount,
                opportunity.dest_price
            )
            
            # Calculate actual profit
            buy_cost = buy_result['total_cost']
            bridge_fee = bridge_result['fee']
            gas_costs = buy_result['gas'] + bridge_result['gas'] + sell_result['gas']
            sell_proceeds = sell_result['proceeds']
            
            net_profit = sell_proceeds - buy_cost - bridge_fee - gas_costs
            net_profit_percent = (net_profit / buy_cost) * 100
            
            logger.info(f"Cross-chain arbitrage completed: profit = ${net_profit:.2f} ({net_profit_percent:.2f}%)")
            
            return {
                'success': True,
                'buy_result': buy_result,
                'bridge_result': bridge_result,
                'sell_result': sell_result,
                'net_profit': net_profit,
                'net_profit_percent': net_profit_percent,
                'total_gas': gas_costs
            }
        
        except Exception as e:
            logger.error(f"Cross-chain arbitrage failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _buy_on_chain(
        self, chain: str, exchange: str, symbol: str, amount: float, price: float
    ) -> dict:
        """Buy tokens on source chain."""
        # Placeholder - integrate with actual exchange
        logger.info(f"Buying {amount} {symbol} on {chain}/{exchange} at ${price}")
        
        return {
            'chain': chain,
            'exchange': exchange,
            'amount': amount,
            'price': price,
            'total_cost': amount * price,
            'gas': amount * price * 0.003  # 0.3% gas estimate
        }
    
    async def _bridge_tokens(self, bridge: Bridge, symbol: str, amount: float) -> dict:
        """Bridge tokens to destination chain."""
        # Placeholder - integrate with actual bridge
        logger.info(f"Bridging {amount} {symbol} via {bridge.name}")
        
        fee = amount * (bridge.fee_percent / 100)
        
        return {
            'bridge': bridge.name,
            'amount': amount,
            'fee': fee,
            'gas': 50,  # Estimated bridge gas cost
            'eta_minutes': bridge.avg_time_minutes
        }
    
    async def _sell_on_chain(
        self, chain: str, exchange: str, symbol: str, amount: float, price: float
    ) -> dict:
        """Sell tokens on destination chain."""
        # Placeholder - integrate with actual exchange
        logger.info(f"Selling {amount} {symbol} on {chain}/{exchange} at ${price}")
        
        return {
            'chain': chain,
            'exchange': exchange,
            'amount': amount,
            'price': price,
            'proceeds': amount * price,
            'gas': amount * price * 0.003  # 0.3% gas estimate
        }
    
    async def get_stats(self) -> dict:
        """Get cross-chain arbitrage statistics."""
        total_chains = len(set(
            chain.split(':')[0] for chain in self.prices.keys()
        ))
        
        total_price_points = sum(len(prices) for prices in self.prices.values())
        
        return {
            'bridges_available': len(self.bridges),
            'chains_monitored': total_chains,
            'price_points': total_price_points,
            'min_profit_threshold': self.min_profit_percent
        }


# Global instance
_cross_chain_arbitrage: Optional[CrossChainArbitrage] = None


def get_cross_chain_arbitrage(bridges: List[Bridge]) -> CrossChainArbitrage:
    """
    Get cross-chain arbitrage instance.
    
    Args:
        bridges: List of available bridges
    
    Returns:
        CrossChainArbitrage instance
    """
    global _cross_chain_arbitrage
    
    if _cross_chain_arbitrage is None:
        _cross_chain_arbitrage = CrossChainArbitrage(bridges=bridges)
    
    return _cross_chain_arbitrage


# Usage example
"""
from core.cross_chain_arbitrage import get_cross_chain_arbitrage, Bridge

# Define bridges
bridges = [
    Bridge('Polygon Bridge', 'ethereum', 'polygon', 0.1, 100, 100000, 10),
    Bridge('Arbitrum Bridge', 'ethereum', 'arbitrum', 0.05, 100, 100000, 15),
    Bridge('Optimism Bridge', 'ethereum', 'optimism', 0.05, 100, 100000, 20),
]

cross_chain = get_cross_chain_arbitrage(bridges)

# Update prices
await cross_chain.update_price('ethereum', 'Uniswap', 'BTC/USDT', 50000)
await cross_chain.update_price('polygon', 'QuickSwap', 'BTC/USDT', 50200)

# Find opportunities
opportunities = await cross_chain.find_opportunities('BTC/USDT')

for opp in opportunities:
    print(f"Opportunity: Buy on {opp.source_chain} at ${opp.source_price}")
    print(f"            Sell on {opp.dest_chain} at ${opp.dest_price}")
    print(f"            Net profit: {opp.net_profit_percent:.2f}%")

# Execute best opportunity
if opportunities:
    result = await cross_chain.execute_arbitrage(opportunities[0], amount=1000)
    print(f"Result: {result}")
"""
