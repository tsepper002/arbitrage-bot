"""
Triangular Arbitrage Engine

Uses USDT-denominated pairs from PriceStore to compute implied cross-rates
and find same-exchange triangular arbitrage cycles.

Example: On Bybit with BTC-USDT and ETH-USDT:
  Implied ETH/BTC rate = ETH_ask / BTC_bid
  If actual ETH/BTC < implied → buy ETH with BTC (underpriced)
  Cycle: USDT → BTC → ETH → USDT

Since we only subscribe to USDT pairs, we compute cross-rates as:
  rate(A/B) = price(A-USDT) / price(B-USDT)
"""

import asyncio
import logging
import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

import settings
from core.exchange_config import EXCHANGE_PARAMS

logger = logging.getLogger(__name__)


@dataclass
class TriangularRoute:
    """Represents a triangular arbitrage route using USDT pairs"""
    pair_a: str   # e.g., "BTC-USDT"
    pair_b: str   # e.g., "ETH-USDT"

    def __str__(self):
        return f"USDT→{self.pair_a}→{self.pair_b}→USDT"


class TriangularArbitrageEngine:
    """
    Same-exchange triangular arbitrage using USDT pairs.

    For each exchange, checks if the implied cross-rate between two
    USDT pairs creates a profitable cycle after 3 legs of fees.

    Cycle (forward): USDT → buy pair_a → implied sell pair_a for pair_b → sell pair_b → USDT
    Using bid/ask: product = (bid_b / ask_a) × (bid_a / ask_b) × (1-fee)^3
    Simplified: product = (bid_a × bid_b) / (ask_a × ask_b) × (1-fee)^3

    In practice, same-exchange triangular with only USDT pairs is equivalent
    to checking if bid_a/ask_a × bid_b/ask_b > 1/(1-fee)^3 — i.e., the
    combined spread product exceeds the 3-leg fee cost. This is rare on
    a single exchange but happens during volatility spikes.
    """

    def __init__(
        self,
        price_store,
        order_executor,
        exchange_config,
        min_profit_pct: float = 0.05,
        enabled_exchanges: List[str] = None
    ):
        self.price_store = price_store
        self.order_executor = order_executor
        self.exchange_config = exchange_config
        self.min_profit_pct = min_profit_pct
        self.enabled_exchanges = enabled_exchanges or []

        self.routes = self._generate_routes()

        # Statistics
        self.total_scans = 0
        self.total_opportunities = 0
        self.best_profit_pct = 0.0

        logger.info(
            f"Triangular arbitrage initialized: {len(self.routes)} routes, "
            f"min_profit={min_profit_pct}%"
        )

    def _generate_routes(self) -> List[TriangularRoute]:
        """Generate triangular routes from common USDT pairs."""
        base_pairs = [
            'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BNB-USDT', 'XRP-USDT',
            'DOGE-USDT', 'LTC-USDT', 'ADA-USDT',
        ]
        routes = []
        for i, a in enumerate(base_pairs):
            for b in base_pairs[i + 1:]:
                routes.append(TriangularRoute(pair_a=a, pair_b=b))
        logger.info(f"Generated {len(routes)} triangular routes")
        return routes

    def scan_opportunities(self) -> List[Dict]:
        """Scan all routes on all enabled exchanges."""
        self.total_scans += 1
        opportunities = []

        snap = self.price_store.snapshot()

        for exchange in self.enabled_exchanges:
            fee = EXCHANGE_PARAMS.get(exchange, {}).get('taker', 0.001)

            for route in self.routes:
                opp = self._check_route(snap, exchange, route, fee)
                if opp:
                    opportunities.append(opp)
                    self.total_opportunities += 1
                    if opp['profit_pct'] > self.best_profit_pct:
                        self.best_profit_pct = opp['profit_pct']

        return opportunities

    def _check_route(self, snap: Dict, exchange: str,
                     route: TriangularRoute, fee: float) -> Optional[Dict]:
        """Check if a triangular route is profitable on given exchange."""
        try:
            rec_a = snap.get(route.pair_a, {}).get(exchange)
            rec_b = snap.get(route.pair_b, {}).get(exchange)
            if not rec_a or not rec_b:
                return None

            bid_a = rec_a.get('bid')
            ask_a = rec_a.get('ask')
            bid_b = rec_b.get('bid')
            ask_b = rec_b.get('ask')

            if not (bid_a and ask_a and bid_b and ask_b):
                return None
            if ask_a <= 0 or ask_b <= 0:
                return None

            # Cycle: USDT → buy A at ask → implied cross → sell B at bid → USDT
            # Forward: product = (bid_a * bid_b) / (ask_a * ask_b) * (1-fee)^3
            product = (bid_a * bid_b) / (ask_a * ask_b) * ((1 - fee) ** 3)
            profit_pct = (product - 1.0) * 100

            if profit_pct > self.min_profit_pct:
                return {
                    'type': 'triangular',
                    'exchange': exchange,
                    'route': str(route),
                    'pair_a': route.pair_a,
                    'pair_b': route.pair_b,
                    'profit_pct': profit_pct,
                    'bid_a': bid_a,
                    'ask_a': ask_a,
                    'bid_b': bid_b,
                    'ask_b': ask_b,
                    'fee': fee,
                    'timestamp': time.time()
                }
            return None
        except (KeyError, TypeError, ZeroDivisionError) as e:
            logger.debug(f"Error checking route {route} on {exchange}: {e}")
            return None

    async def execute_opportunity(self, opportunity: Dict) -> Dict:
        """Execute a triangular arbitrage opportunity via OrderExecutor."""
        exchange = opportunity['exchange']
        logger.info(
            f"🔺 Executing triangular arb on {exchange}: "
            f"{opportunity['route']} (profit: {opportunity['profit_pct']:.3f}%)"
        )

        if self.order_executor:
            # Use real prices from the opportunity
            ask_a = opportunity.get('ask_a', 0)
            bid_a = opportunity.get('bid_a', 0)
            fee = opportunity.get('fee', 0.001)
            profit_pct = opportunity['profit_pct']

            # Compute trade size: use pair_a as the traded symbol
            max_usdt = getattr(settings, 'MAX_EXPOSURE_USDT', 200.0)
            qty = max_usdt / ask_a if ask_a > 0 else 0

            if qty <= 0:
                logger.warning(f"🔺 Triangular arb skipped: invalid qty (ask_a={ask_a})")
                return {'status': 'error', 'message': 'Invalid quantity'}

            # Net profit in USDT for the full triangular cycle
            invested = qty * ask_a
            net = invested * (profit_pct / 100.0)

            trade = {
                'symbol': opportunity.get('pair_a', 'BTC-USDT'),
                'buy_ex': exchange,
                'sell_ex': exchange,
                'qty': qty,
                'buy_avg': ask_a,
                'sell_avg': bid_a,
                'net': net,
                'roi_pct': profit_pct,
                'strategy': 'TRIANGULAR',
            }
            result = await self.order_executor.execute_arbitrage(trade)
            return result

        return {
            'status': 'simulated',
            'type': 'triangular',
            'exchange': exchange,
            'route': opportunity['route'],
            'expected_profit_pct': opportunity['profit_pct'],
        }

    def get_statistics(self) -> Dict:
        """Get scanning statistics."""
        return {
            'enabled_exchanges': self.enabled_exchanges,
            'routes_count': len(self.routes),
            'min_profit_pct': self.min_profit_pct,
            'total_scans': self.total_scans,
            'total_opportunities': self.total_opportunities,
            'best_profit_pct': self.best_profit_pct,
        }


def get_triangular_engine(
    price_store,
    order_executor,
    exchange_config,
    enabled_exchanges: List[str]
) -> TriangularArbitrageEngine:
    """Factory function to create triangular arbitrage engine."""
    return TriangularArbitrageEngine(
        price_store=price_store,
        order_executor=order_executor,
        exchange_config=exchange_config,
        enabled_exchanges=enabled_exchanges
    )
