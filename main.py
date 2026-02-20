#!/usr/bin/env python3
"""
main.py — Cryptocurrency Arbitrage Bot entry point.

Supports two modes:
  - dry-run (default): Safe simulation with virtual capital, no real orders
  - live: Real order placement via authenticated REST API clients

Usage:
    python main.py                  # default (dry-run)
    python main.py --mode dry-run   # explicit dry-run
    python main.py --mode live      # live trading (requires API keys in .env)
"""

# Configure UTF-8 encoding before any output (avoids Windows cp1251 issues)
import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import argparse
import asyncio
import logging
import os
from typing import List, Dict, Optional

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
from core.state import ExchangeState, STATE
from exchanges.bybit_ws import BybitWS
from exchanges.kucoin_ws import KucoinWS
from exchanges.htx_ws import HtxWS
from exchanges.mexc import MEXC
from exchanges.bybit_rest import BybitREST
from utils.telegram import TelegramNotifier
from utils.throttle import Throttle

logger = logging.getLogger("arbitrage_bot")


def _init_rest_clients() -> Dict:
    """
    Initialize authenticated REST API clients for live trading.
    Reads API keys from settings (which loads from .env file or env vars).

    Returns:
        Dict of exchange_name -> REST client instance
    """
    clients: Dict = {}

    # Bybit REST
    if settings.BYBIT_API_KEY and settings.BYBIT_API_SECRET:
        clients["Bybit"] = BybitREST(api_key=settings.BYBIT_API_KEY, api_secret=settings.BYBIT_API_SECRET)
        logger.info("✅ Bybit REST client initialized for live trading")
    else:
        logger.warning("⚠️  Bybit API keys not configured (set ARB_BYBIT_KEY, ARB_BYBIT_SECRET in .env)")

    return clients


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


async def _monitor_exchange_health(interval: float = 30.0):
    """Periodically log exchange health from STATE registry."""
    try:
        while True:
            await asyncio.sleep(interval)
            online = [name for name, st in STATE.items() if st.online]
            offline = [name for name, st in STATE.items() if not st.online]
            if offline:
                logger.warning(f"Exchange health: ✅ {', '.join(online) or 'none'} | ❌ {', '.join(offline)}")
            else:
                logger.debug(f"Exchange health: all {len(online)} online")
    except asyncio.CancelledError:
        return


async def main(args=None):
    # Apply CLI overrides before anything else
    if args is not None:
        apply_cli_overrides(args)

    # Show prominent mode banner immediately
    if settings.DRY_RUN:
        print("🔵 DRY RUN MODE - Safe simulation (no real trades)")
    else:
        print("🔴 LIVE TRADING MODE - Real orders will be placed!")

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

    # Initialize REST clients for live trading
    rest_clients: Dict = {}
    if not settings.DRY_RUN:
        rest_clients = _init_rest_clients()
        if not rest_clients:
            logger.error("🔴 No REST clients configured! Live orders will fail.")
            logger.error("   Set BYBIT_API_KEY/BYBIT_API_SECRET or switch to --mode dry-run")
    else:
        logger.info("🔵 Skipping REST client initialization (dry-run mode)")

    loop = asyncio.get_running_loop()
    store = PriceStore()

    # Register exchange states
    for ex_name in ["Bybit", "KuCoin", "HTX", "MEXC"]:
        STATE[ex_name] = ExchangeState(ex_name)

    # Initialize exchange connections with staggered start
    stagger = 0.1
    logger.info("Initializing exchange connections...")
    bybit = BybitWS(symbols, store, loop, exchange_name="Bybit", stagger_start=stagger)
    STATE["Bybit"].set_online()
    await asyncio.sleep(0.1)
    kucoin = KucoinWS(symbols, store, loop, exchange_name="KuCoin", stagger_start=stagger)
    STATE["KuCoin"].set_online()
    await asyncio.sleep(0.1)
    htx = HtxWS(symbols, store, loop, exchange_name="HTX", stagger_start=stagger)
    STATE["HTX"].set_online()

    mexc = MEXC(store, symbols)
    STATE["MEXC"].set_online()
    mexc_task = asyncio.create_task(mexc.run())

    exchanges = [bybit, kucoin, htx]

    # Start monitoring tasks
    monitor_task = asyncio.create_task(_monitor_store(store))
    health_task = asyncio.create_task(_monitor_exchange_health())

    # Start arbitrage engine (with REST clients for live trading)
    engine = ArbitrageEngine(store, rest_clients=rest_clients)

    # Initialize Telegram notifier
    notifier = TelegramNotifier()
    await notifier.notify_startup(len(symbols), num_exchanges)

    engine_task = asyncio.create_task(engine.run(symbols))

    try:
        await asyncio.gather(engine_task, monitor_task, health_task)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        # Cleanup
        monitor_task.cancel()
        health_task.cancel()
        mexc.stop()
        mexc_task.cancel()
        
        # Print final statistics
        logger.info("\n" + "="*60)
        engine.executor.print_statistics()
        engine.dispatcher.print_stats()
        logger.info("="*60)

        # Send shutdown Telegram notification
        try:
            stats = engine.executor.get_statistics()
            await notifier.send_message(
                f"🛑 Bot stopped\n"
                f"Total trades: {stats['total_orders']}\n"
                f"Total profit: ${stats['total_profit']:.4f}\n"
                f"Mode: {'DRY RUN' if settings.DRY_RUN else 'LIVE'}"
            )
        except Exception:
            pass
        
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