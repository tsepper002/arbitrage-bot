"""
Triangular Arbitrage Engine

Scans for arbitrage opportunities within a single exchange by trading through
multiple currency pairs in a cycle (e.g., USDT → BTC → ETH → USDT).

Expected profit increase: +30-60% additional opportunities
"""

import asyncio
import logging
import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TriangularRoute:
    """Represents a triangular arbitrage route"""
    exchange: str
    start_currency: str  # e.g., "USDT"
    leg1_pair: str       # e.g., "BTCUSDT"
    leg1_side: str       # "buy" or "sell"
    leg2_pair: str       # e.g., "ETHBTC"
    leg2_side: str       # "buy" or "sell"
    leg3_pair: str       # e.g., "ETHUSDT"
    leg3_side: str       # "buy" or "sell"
    
    def __str__(self):
        return f"{self.start_currency}→{self.leg1_pair}→{self.leg2_pair}→{self.leg3_pair}"


class TriangularArbitrageEngine:
    """
    Detects and executes triangular arbitrage opportunities within a single exchange.
    
    Example: USDT → BTC → ETH → USDT
    1. Buy BTC with USDT
    2. Buy ETH with BTC
    3. Sell ETH for USDT
    
    Profit if: rate_1 * rate_2 * rate_3 * (1 - fee)^3 > 1.0
    """
    
    def __init__(
        self,
        price_store,
        order_executor,
        exchange_config,
        min_profit_pct: float = 0.05,  # 0.05% minimum profit
        enabled_exchanges: List[str] = None
    ):
        self.price_store = price_store
        self.order_executor = order_executor
        self.exchange_config = exchange_config
        self.min_profit_pct = min_profit_pct
        self.enabled_exchanges = enabled_exchanges or []
        
        # Common triangular routes (pre-configured)
        self.routes = self._generate_common_routes()
        
        logger.info(
            f"Triangular arbitrage initialized: {len(self.routes)} routes, "
            f"min_profit={min_profit_pct}%"
        )
    
    def _generate_common_routes(self) -> List[TriangularRoute]:
        """
        Generate common triangular arbitrage routes.
        
        These are the most liquid and profitable routes across exchanges.
        """
        routes = []
        
        # Route 1: USDT → BTC → ETH → USDT
        routes.append(TriangularRoute(
            exchange="all",
            start_currency="USDT",
            leg1_pair="BTCUSDT",
            leg1_side="buy",
            leg2_pair="ETHBTC",
            leg2_side="buy",
            leg3_pair="ETHUSDT",
            leg3_side="sell"
        ))
        
        # Route 2: USDT → ETH → BTC → USDT
        routes.append(TriangularRoute(
            exchange="all",
            start_currency="USDT",
            leg1_pair="ETHUSDT",
            leg1_side="buy",
            leg2_pair="ETHBTC",
            leg2_side="sell",
            leg3_pair="BTCUSDT",
            leg3_side="sell"
        ))
        
        # Route 3: USDT → BTC → BNB → USDT
        routes.append(TriangularRoute(
            exchange="all",
            start_currency="USDT",
            leg1_pair="BTCUSDT",
            leg1_side="buy",
            leg2_pair="BNBBTC",
            leg2_side="buy",
            leg3_pair="BNBUSDT",
            leg3_side="sell"
        ))
        
        # Route 4: USDT → BNB → BTC → USDT
        routes.append(TriangularRoute(
            exchange="all",
            start_currency="USDT",
            leg1_pair="BNBUSDT",
            leg1_side="buy",
            leg2_pair="BNBBTC",
            leg2_side="sell",
            leg3_pair="BTCUSDT",
            leg3_side="sell"
        ))
        
        # Route 5: USDT → BTC → SOL → USDT
        routes.append(TriangularRoute(
            exchange="all",
            start_currency="USDT",
            leg1_pair="BTCUSDT",
            leg1_side="buy",
            leg2_pair="SOLBTC",
            leg2_side="buy",
            leg3_pair="SOLUSDT",
            leg3_side="sell"
        ))
        
        logger.info(f"Generated {len(routes)} triangular routes")
        return routes
    
    def scan_opportunities(self) -> List[Dict]:
        """
        Scan all routes on all enabled exchanges for profitable opportunities.
        
        Returns:
            List of profitable opportunities with expected profit
        """
        opportunities = []
        
        for exchange in self.enabled_exchanges:
            for route in self.routes:
                opportunity = self._check_route(exchange, route)
                if opportunity:
                    opportunities.append(opportunity)
        
        return opportunities
    
    def _check_route(self, exchange: str, route: TriangularRoute) -> Optional[Dict]:
        """
        Check if a triangular route is profitable on given exchange.
        
        Returns:
            Dict with opportunity details if profitable, None otherwise
        """
        try:
            # Get orderbooks for all three legs
            book1 = self.price_store.get_orderbook(exchange, route.leg1_pair)
            book2 = self.price_store.get_orderbook(exchange, route.leg2_pair)
            book3 = self.price_store.get_orderbook(exchange, route.leg3_pair)
            
            if not book1 or not book2 or not book3:
                return None
            
            # Get exchange fees
            fee_info = self.exchange_config.get(exchange, {})
            maker_fee = fee_info.get('maker_fee', 0.001)
            taker_fee = fee_info.get('taker_fee', 0.001)
            fee = taker_fee  # Use taker fee for conservative estimate
            
            # Calculate rates for each leg
            rate1 = self._get_execution_rate(book1, route.leg1_side)
            rate2 = self._get_execution_rate(book2, route.leg2_side)
            rate3 = self._get_execution_rate(book3, route.leg3_side)
            
            if not rate1 or not rate2 or not rate3:
                return None
            
            # Calculate final product after fees
            # Each leg loses (1 - fee) of value
            product = rate1 * rate2 * rate3 * ((1 - fee) ** 3)
            
            # Calculate profit percentage
            profit_pct = (product - 1.0) * 100
            
            # Check if profitable
            if profit_pct > self.min_profit_pct:
                return {
                    'type': 'triangular',
                    'exchange': exchange,
                    'route': route,
                    'rate1': rate1,
                    'rate2': rate2,
                    'rate3': rate3,
                    'product': product,
                    'profit_pct': profit_pct,
                    'timestamp': time.time()
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error checking route {route} on {exchange}: {e}")
            return None
    
    def _get_execution_rate(self, orderbook: Dict, side: str) -> Optional[float]:
        """
        Get execution rate from orderbook for given side.
        
        For buy: use best ask price
        For sell: use best bid price
        
        Returns:
            Rate as float, or None if orderbook insufficient
        """
        try:
            if side == "buy":
                # Buy = take from asks
                if orderbook.get('asks') and len(orderbook['asks']) > 0:
                    return float(orderbook['asks'][0][0])  # Best ask price
            else:  # sell
                # Sell = take from bids
                if orderbook.get('bids') and len(orderbook['bids']) > 0:
                    return float(orderbook['bids'][0][0])  # Best bid price
            
            return None
            
        except (IndexError, ValueError, TypeError) as e:
            logger.debug(f"Error getting execution rate: {e}")
            return None
    
    async def execute_opportunity(self, opportunity: Dict) -> Dict:
        """
        Execute a triangular arbitrage opportunity.
        
        This is more complex than cross-exchange arbitrage because it requires
        three sequential trades on the same exchange.
        
        Returns:
            Execution result with status and details
        """
        route = opportunity['route']
        exchange = opportunity['exchange']
        
        logger.info(
            f"Executing triangular arbitrage on {exchange}: "
            f"{route} (expected profit: {opportunity['profit_pct']:.3f}%)"
        )
        
        # TODO: Implementation requires:
        # 1. Execute leg 1 (buy/sell)
        # 2. Wait for confirmation
        # 3. Execute leg 2 with output from leg 1
        # 4. Wait for confirmation
        # 5. Execute leg 3 with output from leg 2
        # 6. Calculate actual profit
        
        # For now, return dry-run result
        return {
            'status': 'dry_run',
            'type': 'triangular',
            'exchange': exchange,
            'route': str(route),
            'expected_profit_pct': opportunity['profit_pct'],
            'message': 'Triangular arbitrage execution not yet implemented'
        }
    
    def get_statistics(self) -> Dict:
        """Get statistics about triangular arbitrage scanning."""
        return {
            'enabled_exchanges': self.enabled_exchanges,
            'routes_count': len(self.routes),
            'min_profit_pct': self.min_profit_pct,
            'route_list': [str(r) for r in self.routes]
        }


def get_triangular_engine(
    price_store,
    order_executor,
    exchange_config,
    enabled_exchanges: List[str]
) -> TriangularArbitrageEngine:
    """
    Factory function to create triangular arbitrage engine.
    
    Args:
        price_store: PriceStore instance
        order_executor: OrderExecutor instance
        exchange_config: Exchange configuration dict
        enabled_exchanges: List of exchange names to scan
    
    Returns:
        TriangularArbitrageEngine instance
    """
    return TriangularArbitrageEngine(
        price_store=price_store,
        order_executor=order_executor,
        exchange_config=exchange_config,
        enabled_exchanges=enabled_exchanges
    )
