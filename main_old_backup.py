#!/usr/bin/env python3
"""
main.py — diagnostic monitor + startup.
Enhanced with health monitoring and configurable settings.
UPDATED: Now supports 4 exchanges (Bybit, KuCoin, HTX, MEXC)
"""
import asyncio
import logging
from typing import List
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.price_store import PriceStore
from core.arbitrage import ArbitrageEngine
from exchanges.bybit_ws import BybitWS
from exchanges.kucoin_ws import KucoinWS
from exchanges.htx_ws import HtxWS
from exchanges.mexc_ws import MexcWS
import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("arbitrage_bot")

# Print configuration at startup
logger.info("\n" + settings.get_config_summary())


async def _monitor_store(store: PriceStore, interval: float = None):
    """
    Prints order book information with reduced frequency to minimize log spam.
    Configurable via settings.MONITOR_INTERVAL_SEC
    """
    if interval is None:
        interval = settings.MONITOR_INTERVAL_SEC
    
    try:
        while True:
            snap = store.snapshot()
            if not snap:
                logger.debug("[STORE] empty")
            else:
                # Only print summary, not full details
                total_exchanges = sum(len(exmap) for exmap in snap.values())
                logger.info(f"[STORE] Tracking {len(snap)} symbols across {total_exchanges} exchange connections")
                
                # Print detailed info only at DEBUG level
                if logger.isEnabledFor(logging.DEBUG):
                    for s, exmap in snap.items():
                        parts = []
                        for ex, rec in exmap.items():
                            b_len = len(rec.get("bids_levels", []))
                            a_len = len(rec.get("asks_levels", []))
                            top_bid = rec.get("bid")
                            top_ask = rec.get("ask")
                            parts.append(f"{ex}: bid={top_bid} ask={top_ask} levels={b_len}/{a_len}")
                        logger.debug(f"[STORE] {s}: " + " | ".join(parts))
            
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        return


async def main():
    # Use symbols from settings
    symbols: List[str] = settings.TRADING_SYMBOLS

    logger.info(f"Starting arbitrage bot for {len(symbols)} symbols: {', '.join(symbols)}")

    loop = asyncio.get_running_loop()
    store = PriceStore()

    # Initialize exchange connections with staggered start
    # NOW SUPPORTS 4 EXCHANGES: Bybit, KuCoin, HTX, MEXC
    stagger = 0.1
    logger.info("Initializing 4 exchange connections...")
    bybit = BybitWS(symbols, store, loop, exchange_name="Bybit", stagger_start=stagger)
    await asyncio.sleep(0.1)
    kucoin = KucoinWS(symbols, store, loop, exchange_name="KuCoin", stagger_start=stagger)
    await asyncio.sleep(0.1)
    htx = HtxWS(symbols, store, loop, exchange_name="HTX", stagger_start=stagger)
    await asyncio.sleep(0.1)
    mexc = MexcWS(symbols, store, loop, exchange_name="MEXC", stagger_start=stagger)
    
    exchanges = [bybit, kucoin, htx, mexc]
    logger.info(f"✅ All {len(exchanges)} exchanges initialized")

    # Start monitoring task
    monitor_task = asyncio.create_task(_monitor_store(store))

    # Start arbitrage engine
    engine = ArbitrageEngine(store)
    engine_task = asyncio.create_task(engine.run(symbols))

    try:
        await asyncio.gather(engine_task, monitor_task)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        # Cleanup
        monitor_task.cancel()
        
        # Print final statistics
        logger.info("\n" + "="*60)
        engine.executor.print_statistics()
        logger.info("="*60)
        
        # Stop exchange connections
        for c in exchanges:
            try:
                c.stop()
            except Exception as e:
                logger.exception(f"Error stopping client: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass