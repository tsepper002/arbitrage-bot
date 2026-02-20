#!/usr/bin/env python3
"""
main.py — diagnostic monitor + startup.
Enhanced with health monitoring and configurable settings.

Usage:
    python main.py                  # default (dry-run)
    python main.py --mode dry-run   # explicit dry-run
    python main.py --mode live      # live trading (requires setup)
"""
import argparse
import asyncio
import logging
from typing import List
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import settings


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Cryptocurrency Arbitrage Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python main.py --mode dry-run      Run in safe simulation mode\n"
               "  python main.py --mode live          Run with real orders (requires setup)\n"
               "  python main.py --symbols BTC-USDT,ETH-USDT\n",
    )
    parser.add_argument(
        "--mode",
        choices=["dry-run", "live"],
        default=None,
        help="Execution mode: 'dry-run' (default, safe) or 'live' (real orders)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated trading pairs, e.g. BTC-USDT,ETH-USDT",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Override log level",
    )
    return parser.parse_args(argv)


def apply_cli_overrides(args):
    """Apply CLI arguments as overrides to settings module."""
    if args.mode is not None:
        settings.DRY_RUN = args.mode == "dry-run"
    if args.symbols is not None:
        parsed = [s.strip() for s in args.symbols.split(",") if s.strip()]
        if parsed:
            settings.TRADING_SYMBOLS = parsed
    if args.log_level is not None:
        settings.LOG_LEVEL = args.log_level


from core.price_store import PriceStore
from core.arbitrage import ArbitrageEngine
from exchanges.bybit_ws import BybitWS
from exchanges.kucoin_ws import KucoinWS
from exchanges.htx_ws import HtxWS
from exchanges.mexc import MEXC
from utils.telegram import TelegramNotifier

logger = logging.getLogger("arbitrage_bot")


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


async def main(args=None):
    # Apply CLI overrides before anything else
    if args is not None:
        apply_cli_overrides(args)

    # Configure logging (after overrides)
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Print configuration at startup
    logger.info("\n" + settings.get_config_summary())

    # Use symbols from settings
    symbols: List[str] = settings.TRADING_SYMBOLS

    num_exchanges = 4  # Bybit, KuCoin, HTX, MEXC
    logger.info(f"Starting arbitrage bot with {num_exchanges} exchanges for {len(symbols)} symbols: {', '.join(symbols)}")

    loop = asyncio.get_running_loop()
    store = PriceStore()

    # Initialize exchange connections with staggered start
    stagger = 0.1
    logger.info("Initializing exchange connections...")
    bybit = BybitWS(symbols, store, loop, exchange_name="Bybit", stagger_start=stagger)
    await asyncio.sleep(0.1)
    kucoin = KucoinWS(symbols, store, loop, exchange_name="KuCoin", stagger_start=stagger)
    await asyncio.sleep(0.1)
    htx = HtxWS(symbols, store, loop, exchange_name="HTX", stagger_start=stagger)

    mexc = MEXC(store, symbols)
    mexc_task = asyncio.create_task(mexc.run())

    exchanges = [bybit, kucoin, htx]

    # Start monitoring task
    monitor_task = asyncio.create_task(_monitor_store(store))

    # Start arbitrage engine
    engine = ArbitrageEngine(store)

    # Initialize Telegram notifier
    notifier = TelegramNotifier()
    await notifier.notify_startup(len(symbols), num_exchanges)

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
        mexc.stop()
        mexc_task.cancel()
        
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
        cli_args = parse_args()
        asyncio.run(main(cli_args))
    except KeyboardInterrupt:
        pass