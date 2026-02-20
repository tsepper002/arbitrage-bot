"""
Strategy dispatcher – runs all 14 strategies and merges results.

Fast strategies run every scan cycle.
Slow strategies run periodically (every SLOW_INTERVAL_SEC seconds).
"""
import asyncio
import time
import logging
from typing import List, Dict

from .strategies import ALL_STRATEGIES, FAST_STRATEGIES, SLOW_STRATEGIES
import settings

logger = logging.getLogger("strategy_dispatcher")


class StrategyDispatcher:
    """Dispatches all 14 strategies and merges results by priority."""

    def __init__(self, store):
        self.store = store
        self.strategies = ALL_STRATEGIES
        self._last_slow_run = 0.0
        self._slow_interval = 10.0  # run slow strategies every 10 seconds
        self._stats: Dict[str, Dict] = {
            s.strategy_type: {"scans": 0, "opportunities": 0, "total_net": 0.0}
            for s in self.strategies
        }
        logger.info(f"StrategyDispatcher initialized with {len(self.strategies)} strategies")
        logger.info(f"  Fast strategies ({len(FAST_STRATEGIES)}): {', '.join(s.strategy_type for s in FAST_STRATEGIES)}")
        logger.info(f"  Slow strategies ({len(SLOW_STRATEGIES)}): {', '.join(s.strategy_type for s in SLOW_STRATEGIES)}")

    async def scan_all(self, symbols: List[str]) -> List[Dict]:
        """
        Run all applicable strategies and return merged, deduplicated results.

        Returns:
            List of opportunity dicts sorted by net profit (descending).
        """
        now = time.time()
        all_opps: List[Dict] = []

        # Always run fast strategies
        for strategy in FAST_STRATEGIES:
            if strategy.strategy_type == "CROSS_EXCHANGE":
                continue  # handled by ArbitrageEngine.scan_once()

            try:
                opps = await strategy.scan(self.store, symbols)
                self._stats[strategy.strategy_type]["scans"] += 1
                self._stats[strategy.strategy_type]["opportunities"] += len(opps)
                for o in opps:
                    o.setdefault("strategy", strategy.strategy_type)
                    self._stats[strategy.strategy_type]["total_net"] += o.get("net", 0)
                all_opps.extend(opps)
            except Exception as e:
                logger.debug(f"Strategy {strategy.strategy_type} error: {e}")

        # Run slow strategies periodically
        if now - self._last_slow_run >= self._slow_interval:
            self._last_slow_run = now
            for strategy in SLOW_STRATEGIES:
                try:
                    opps = await strategy.scan(self.store, symbols)
                    self._stats[strategy.strategy_type]["scans"] += 1
                    self._stats[strategy.strategy_type]["opportunities"] += len(opps)
                    for o in opps:
                        o.setdefault("strategy", strategy.strategy_type)
                        self._stats[strategy.strategy_type]["total_net"] += o.get("net", 0)
                    all_opps.extend(opps)
                except Exception as e:
                    logger.debug(f"Strategy {strategy.strategy_type} error: {e}")

        # Sort all opportunities by net profit
        all_opps.sort(key=lambda x: x.get("net", 0), reverse=True)

        # Limit total
        max_opps = settings.MAX_CONCURRENT_OPPORTUNITIES
        if len(all_opps) > max_opps:
            all_opps = all_opps[:max_opps]

        return all_opps

    def get_stats(self) -> Dict[str, Dict]:
        """Return per-strategy statistics."""
        return dict(self._stats)

    def print_stats(self):
        """Print strategy performance summary."""
        print(f"\n{'='*70}")
        print(f"  STRATEGY DISPATCHER — {len(self.strategies)} STRATEGIES")
        print(f"{'='*70}")
        for s in self.strategies:
            st = self._stats.get(s.strategy_type, {})
            scans = st.get("scans", 0)
            opps = st.get("opportunities", 0)
            net = st.get("total_net", 0)
            print(f"  {s.strategy_type:20s} scans={scans:5d}  opps={opps:4d}  net=${net:.4f}")
        print(f"{'='*70}\n")
