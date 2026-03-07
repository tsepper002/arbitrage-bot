"""
Cross-exchange liquidity analyzer.

Computes per-symbol, per-exchange, and global liquidity metrics used by
the arbitrage scanner and strategy dispatcher to avoid illiquid markets.
"""
import logging
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LiquidityAnalyzer:
    """Analyzes orderbook liquidity across multiple exchanges.

    Maintains a cache of liquidity snapshots keyed by (symbol, exchange)
    and exposes aggregate cross-exchange metrics.
    """

    # Minimum USDT-equivalent depth on both sides to consider a market liquid
    MIN_DEPTH_USDT = 500.0
    # Maximum age before a snapshot is considered stale (seconds)
    MAX_AGE_SEC = 10.0

    def __init__(self):
        # {(symbol, exchange): {metrics + ts}}
        self._cache: Dict[Tuple[str, str], Dict] = {}

    # ------------------------------------------------------------------
    # Single orderbook analysis
    # ------------------------------------------------------------------

    def analyze_orderbook(
        self,
        orderbook: Dict,
        symbol: str = '',
        exchange: str = '',
    ) -> Dict:
        """Analyze a single orderbook snapshot.

        Args:
            orderbook: dict with 'bids' and 'asks' as lists of [price, qty]
            symbol: trading pair (e.g. 'BTC-USDT')
            exchange: exchange name

        Returns:
            dict with bid_depth, ask_depth, spread, spread_bps,
            liquidity_score, mid_price, sufficient_liquidity
        """
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            empty = {
                'bid_depth': 0, 'ask_depth': 0, 'spread': 0,
                'spread_bps': 0, 'liquidity_score': 0, 'mid_price': 0,
                'sufficient_liquidity': False,
            }
            return empty

        bid_depth = self._depth_usdt(bids, 10)
        ask_depth = self._depth_usdt(asks, 10)
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid_price = (best_bid + best_ask) / 2 if (best_bid and best_ask) else 0
        spread = best_ask - best_bid
        spread_bps = (spread / mid_price * 10000) if mid_price > 0 else 0

        score = min((bid_depth + ask_depth) / 10000 * 100, 100)
        sufficient = (bid_depth >= self.MIN_DEPTH_USDT
                      and ask_depth >= self.MIN_DEPTH_USDT
                      and spread_bps < 50)

        result = {
            'bid_depth': bid_depth,
            'ask_depth': ask_depth,
            'spread': spread,
            'spread_bps': spread_bps,
            'mid_price': mid_price,
            'liquidity_score': score,
            'sufficient_liquidity': sufficient,
            'ts': time.time(),
        }

        if symbol and exchange:
            self._cache[(symbol, exchange)] = result
        return result

    # ------------------------------------------------------------------
    # Cross-exchange aggregation
    # ------------------------------------------------------------------

    def get_cross_exchange_liquidity(self, symbol: str) -> Dict:
        """Aggregate liquidity across ALL exchanges for a given symbol.

        Returns total bid/ask depth, number of liquid exchanges, and
        a composite liquidity score.
        """
        now = time.time()
        total_bid = 0.0
        total_ask = 0.0
        liquid_exchanges: List[str] = []

        for (sym, ex), snap in self._cache.items():
            if sym != symbol:
                continue
            if now - snap.get('ts', 0) > self.MAX_AGE_SEC:
                continue
            total_bid += snap['bid_depth']
            total_ask += snap['ask_depth']
            if snap.get('sufficient_liquidity'):
                liquid_exchanges.append(ex)

        return {
            'symbol': symbol,
            'total_bid_depth': total_bid,
            'total_ask_depth': total_ask,
            'liquid_exchanges': liquid_exchanges,
            'num_liquid_exchanges': len(liquid_exchanges),
            'composite_score': min((total_bid + total_ask) / 50000 * 100, 100),
        }

    def rank_symbols_by_liquidity(
        self, symbols: List[str]
    ) -> List[Tuple[str, float]]:
        """Rank symbols by composite cross-exchange liquidity score."""
        scored = []
        for sym in symbols:
            info = self.get_cross_exchange_liquidity(sym)
            scored.append((sym, info['composite_score']))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _depth_usdt(levels: List, n: int = 10) -> float:
        """Sum notional (price × qty) for the top *n* book levels."""
        total = 0.0
        for price, qty in levels[:n]:
            total += float(price) * float(qty)
        return total
