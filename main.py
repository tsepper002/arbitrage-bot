#!/usr/bin/env python3
"""
main.py — diagnostic monitor + startup.
Runs WS clients for multiple exchanges and monitors for arbitrage opportunities.
"""
import asyncio
import logging
import os
import sys
from typing import List

# Support both direct execution and module imports
try:
    from .core.price_store import PriceStore
    from .core.arbitrage import ArbitrageEngine
    from .exchanges.bybit_ws import BybitWS
    from .exchanges.kucoin_ws import KucoinWS
    from .exchanges.htx_ws import HtxWS
except ImportError:
    from core.price_store import PriceStore
    from core.arbitrage import ArbitrageEngine
    from exchanges.bybit_ws import BybitWS
    from exchanges.kucoin_ws import KucoinWS
    from exchanges.htx_ws import HtxWS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("arbitrage_bot")


async def _monitor_store(store: PriceStore, interval: float = 2.0):
    """
    Печатает расширенную информацию о snapshot: для каждой пары — какие биржи есть,
    и для каждой биржи — есть ли bids_levels/asks_levels и их длина.
    """
    try:
        while True:
            snap = store.snapshot()
            if not snap:
                print("[STORE] empty")
            else:
                for s, exmap in snap.items():
                    parts = []
                    for ex, rec in exmap.items():
                        has_b = "bids_levels" in rec
                        has_a = "asks_levels" in rec
                        b_len = len(rec.get("bids_levels", []))
                        a_len = len(rec.get("asks_levels", []))
                        top_bid = rec.get("bid")
                        top_ask = rec.get("ask")
                        parts.append(f"{ex}: bid={top_bid} ask={top_ask} bids_levels={b_len} asks_levels={a_len}")
                    print(f"[STORE] {s}: " + " | ".join(parts))
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        return


async def main():
    """Main entry point for the arbitrage bot."""
    # Check for paper mode (default is paper mode)
    paper_mode = os.getenv("PAPER_MODE", "1") == "1"
    if paper_mode:
        logger.info("="*60)
        logger.info("RUNNING IN PAPER MODE - No real trades will be executed")
        logger.info("="*60)
    else:
        logger.warning("LIVE MODE - Real trading is NOT implemented yet!")
        logger.warning("Exiting for safety. Use PAPER_MODE=1 to run in paper mode.")
        return
    
    symbols: List[str] = [
        "BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "XRP-USDT",
        "DOGE-USDT", "LTC-USDT", "ADA-USDT", "MATIC-USDT", "DOT-USDT",
    ]

    logger.info(f"Initializing arbitrage bot with {len(symbols)} symbols")
    loop = asyncio.get_running_loop()
    
    # Initialize the canonical PriceStore
    store = PriceStore()
    logger.info("PriceStore initialized")

    # Initialize exchange WS clients with staggered start times
    stagger = 0.1
    clients = []
    
    try:
        logger.info("Initializing exchange WebSocket clients...")
        bybit = BybitWS(symbols, store, loop, exchange_name="Bybit", stagger_start=0)
        clients.append(("Bybit", bybit))
        
        await asyncio.sleep(stagger)
        kucoin = KucoinWS(symbols, store, loop, exchange_name="KuCoin", stagger_start=0)
        clients.append(("KuCoin", kucoin))
        
        await asyncio.sleep(stagger)
        htx = HtxWS(symbols, store, loop, exchange_name="HTX", stagger_start=0)
        clients.append(("HTX", htx))
        
        logger.info(f"Initialized {len(clients)} exchange clients")
    except Exception as e:
        logger.exception(f"Error initializing clients: {e}")
        return

    # Start monitoring task
    monitor_task = asyncio.create_task(_monitor_store(store, interval=3.0))
    logger.info("Store monitor started")

    # Start arbitrage engine
    engine = ArbitrageEngine(store)
    engine_task = asyncio.create_task(engine.run(symbols))
    logger.info("Arbitrage engine started")
    
    logger.info("All systems operational. Press Ctrl+C to stop.")

    try:
        # Run until interrupted
        await asyncio.gather(engine_task, monitor_task)
    except asyncio.CancelledError:
        logger.info("Received cancellation signal")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.exception(f"Unexpected error in main loop: {e}")
    finally:
        logger.info("Shutting down...")
        
        # Cancel tasks gracefully
        monitor_task.cancel()
        engine_task.cancel()
        
        try:
            await asyncio.gather(monitor_task, engine_task, return_exceptions=True)
        except Exception:
            pass
        
        # Stop all exchange clients
        for name, client in clients:
            try:
                logger.info(f"Stopping {name} client...")
                client.stop()
            except Exception as e:
                logger.error(f"Error stopping {name} client: {e}")
        
        # Give threads time to clean up
        await asyncio.sleep(0.5)
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        logger.info("Starting Arbitrage Bot...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)