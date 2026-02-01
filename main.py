#!/usr/bin/env python3
"""
main.py — diagnostic monitor + startup.
"""
import asyncio
import logging
from typing import List

from core.price_store import PriceStore
from core.arbitrage import ArbitrageEngine
from exchanges.bybit_ws import BybitWS
from exchanges.kucoin_ws import KucoinWS
from exchanges.htx_ws import HtxWS

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
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
    symbols: List[str] = [
        "BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "XRP-USDT",
        "DOGE-USDT", "LTC-USDT", "ADA-USDT", "MATIC-USDT", "DOT-USDT",
    ]

    loop = asyncio.get_running_loop()
    store = PriceStore()

    stagger = 0.1
    bybit = BybitWS(symbols, store, loop, exchange_name="Bybit", stagger_start=stagger)
    await asyncio.sleep(0.1)
    kucoin = KucoinWS(symbols, store, loop, exchange_name="KuCoin", stagger_start=stagger)
    await asyncio.sleep(0.1)
    htx = HtxWS(symbols, store, loop, exchange_name="HTX", stagger_start=stagger)

    monitor_task = asyncio.create_task(_monitor_store(store, interval=2.0))

    engine = ArbitrageEngine(store)
    engine_task = asyncio.create_task(engine.run(symbols))

    try:
        await asyncio.gather(engine_task, monitor_task)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        monitor_task.cancel()
        for c in (bybit, kucoin, htx):
            try:
                c.stop()
            except Exception:
                logger.exception("Error stopping client")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass