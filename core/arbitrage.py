# Updated arbitrage engine: auto qty selection from topK liquidity, safety factor, exposure cap reads from config.
import asyncio
import csv
import os
import time
from typing import List, Tuple, Optional, Dict
from .exchange_config import EXCHANGE_PARAMS
from . import trader_config

def simulate_execution_from_book(levels: List[Tuple[float, float]], qty: float) -> Tuple[float, float]:
    remaining = qty
    cost = 0.0
    filled = 0.0
    for price, size in levels:
        take = min(size, remaining)
        cost += take * price
        remaining -= take
        filled += take
        if remaining <= 1e-12:
            break
    if filled == 0:
        return 0.0, 0.0
    avg = cost / filled
    return avg, filled

class ArbitrageEngine:
    def __init__(self, store, *,
                 default_qty: float = 0.001,
                 min_net_pct: float = 0.05,
                 persist_path: str = "arbs.csv",
                 max_exposure_usdt: float | None = None,
                 safety_factor: float = 0.5,
                 topk: int = 20):
        self.store = store
        self.params = EXCHANGE_PARAMS
        self.default_qty = default_qty
        self.min_net_pct = min_net_pct
        self.persist_path = persist_path
        self.safety_factor = safety_factor
        self.topk = topk

        # max exposure: if not provided, try to compute from trader_config (RUB -> USDT), otherwise default to 200 USDT
        if max_exposure_usdt is not None:
            self.max_exposure_usdt = max_exposure_usdt
        else:
            sc_usdt = trader_config.get_starting_capital_usdt(None)
            if sc_usdt:
                # conservative: use 50% of starting capital as per-trade max exposure
                self.max_exposure_usdt = max(sc_usdt * 0.5, 50.0)
            else:
                self.max_exposure_usdt = 200.0

        # ensure persistence file
        if not os.path.exists(self.persist_path):
            with open(self.persist_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["ts", "symbol", "buy_ex", "sell_ex", "qty", "buy_price", "sell_price", "net", "roi_pct"])

        self.recent_cache = {}

    def _fee_rate(self, exchange: str, side: str = "taker") -> float:
        p = self.params.get(exchange, {})
        if side == "maker":
            return p.get("maker", 0.0)
        return p.get("taker", p.get("taker", 0.002))

    def _persist_opportunity(self, info: Dict):
        try:
            with open(self.persist_path, "a", newline="") as f:
                w = csv.writer(f)
                w.writerow([time.time(), info["symbol"], info["buy_ex"], info["sell_ex"],
                            info["qty"], info["buy_avg"], info["sell_avg"], info["net"], info["roi_pct"]])
        except Exception:
            pass

    def _choose_qty(self, buy_levels, sell_levels, buy_price) -> float:
        """
        Choose qty based on available liquidity across topK levels, safety factor and exposure cap.
        buy_levels: asks ascending list [(price,size),...]
        sell_levels: bids descending list [(price,size),...]
        buy_price: current buy price (best ask)
        """
        # total available at topK (base asset)
        avail_buy = sum(s for p, s in buy_levels[:self.topk]) if buy_levels else 0.0
        avail_sell = sum(s for p, s in sell_levels[:self.topk]) if sell_levels else 0.0
        total_avail = min(avail_buy, avail_sell)

        # limit by safety factor
        allowed_by_liquidity = total_avail * self.safety_factor

        # limit by exposure in USDT
        if buy_price and buy_price > 0:
            allowed_by_exposure = self.max_exposure_usdt / buy_price
        else:
            allowed_by_exposure = self.default_qty  # fallback

        # final qty
        qty = min(self.default_qty, allowed_by_liquidity if allowed_by_liquidity > 0 else self.default_qty, allowed_by_exposure)
        # enforce small positive
        return max(qty, 0.0)

    async def scan_once(self, symbol: str, prefunded: bool = True) -> List[Dict]:
        snap = self.store.snapshot()
        exmap = snap.get(symbol, {})
        exchanges = list(exmap.keys())
        res = []
        if len(exchanges) < 2:
            return res

        for i, buy_ex in enumerate(exchanges):
            for sell_ex in exchanges[i+1:]:
                buy = exmap.get(buy_ex, {})
                sell = exmap.get(sell_ex, {})

                asks = buy.get("asks_levels")
                bids = sell.get("bids_levels")

                if not asks:
                    a = buy.get("ask")
                    a_size = buy.get("ask_size") or 0.0
                    asks = [(a, a_size)] if a is not None else []
                if not bids:
                    b = sell.get("bid")
                    b_size = sell.get("bid_size") or 0.0
                    bids = [(b, b_size)] if b is not None else []

                if not asks or not bids:
                    continue

                # choose qty adaptively
                buy_price_est = asks[0][0] if asks else None
                qty = self._choose_qty(asks, bids, buy_price_est)
                if qty <= 0:
                    continue

                buy_avg, buy_filled = simulate_execution_from_book(asks, qty)
                sell_avg, sell_filled = simulate_execution_from_book(bids, qty)
                filled = min(buy_filled, sell_filled)
                if filled <= 0:
                    continue

                buy_fee = self._fee_rate(buy_ex, "taker")
                sell_fee = self._fee_rate(sell_ex, "taker")
                fees = (buy_avg * filled) * buy_fee + (sell_avg * filled) * sell_fee

                gross = (sell_avg - buy_avg) * filled
                net = gross - fees

                invested = buy_avg * filled
                roi_pct = (net / invested) * 100 if invested else 0.0

                info = {
                    "symbol": symbol,
                    "buy_ex": buy_ex,
                    "sell_ex": sell_ex,
                    "qty": filled,
                    "buy_avg": buy_avg,
                    "sell_avg": sell_avg,
                    "gross": gross,
                    "fees": fees,
                    "net": net,
                    "roi_pct": roi_pct,
                }

                if net > 0 and roi_pct >= self.min_net_pct:
                    # dedupe and persist
                    key = f"{symbol}:{buy_ex}->{sell_ex}:{round(buy_avg,6)}:{round(sell_avg,6)}"
                    now = time.time()
                    last_ts = self.recent_cache.get(key, 0)
                    if now - last_ts > 5.0:
                        self.recent_cache[key] = now
                        self._persist_opportunity(info)
                        res.append(info)
        res.sort(key=lambda x: x["net"], reverse=True)
        return res

    async def run(self, symbols: List[str]):
        while True:
            for s in symbols:
                snap = self.store.snapshot()
                exmap = snap.get(s, {})
                best_bid = (None, 0.0)
                best_ask = (None, float("inf"))
                for ex, rec in exmap.items():
                    b = rec.get("bid")
                    a = rec.get("ask")
                    if b and (best_bid[0] is None or b > best_bid[1]):
                        best_bid = (ex, b)
                    if a and (best_ask[0] is None or a < best_ask[1]):
                        best_ask = (ex, a)
                if best_bid[0] or best_ask[0]:
                    print(f"MARKET {s}: BEST_BID {best_bid[0] or '-'} {best_bid[1]} BEST_ASK {best_ask[0] or '-'} {best_ask[1]}")

                opps = await self.scan_once(s)
                if opps:
                    for o in opps[:5]:
                        print(f"ARBITRAGE {s}: BUY@{o['buy_ex']} {o['buy_avg']:.6f} SELL@{o['sell_ex']} {o['sell_avg']:.6f} QTY {o['qty']:.6f} NET {o['net']:.6f} ROI {o['roi_pct']:.3f}%")
            await asyncio.sleep(1.0)