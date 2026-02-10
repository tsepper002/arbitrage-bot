# Updated arbitrage engine: auto qty selection from topK liquidity, safety factor, exposure cap reads from config.
import asyncio
import csv
import os
import time
import logging
from typing import List, Tuple, Optional, Dict, Set
from .exchange_config import EXCHANGE_PARAMS
from . import trader_config
from .order_executor import OrderExecutor
import settings

logger = logging.getLogger("arbitrage_engine")

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
                 default_qty: Optional[float] = None,
                 min_net_pct: Optional[float] = None,
                 persist_path: Optional[str] = None,
                 max_exposure_usdt: Optional[float] = None,
                 safety_factor: Optional[float] = None,
                 topk: Optional[int] = None):
        self.store = store
        self.params = EXCHANGE_PARAMS
        
        # Use settings.py values as defaults
        self.default_qty = default_qty if default_qty is not None else settings.DEFAULT_QUANTITY
        self.min_net_pct = min_net_pct if min_net_pct is not None else settings.MIN_NET_ROI_PCT
        self.persist_path = persist_path if persist_path is not None else settings.OPPORTUNITIES_CSV_PATH
        self.safety_factor = safety_factor if safety_factor is not None else settings.SAFETY_FACTOR
        self.topk = topk if topk is not None else settings.ORDERBOOK_TOP_K

        # max exposure: use settings or compute from trader_config
        if max_exposure_usdt is not None:
            self.max_exposure_usdt = max_exposure_usdt
        elif settings.MAX_EXPOSURE_USDT:
            self.max_exposure_usdt = settings.MAX_EXPOSURE_USDT
        else:
            sc_usdt = trader_config.get_starting_capital_usdt(None)
            if sc_usdt:
                # conservative: use 50% of starting capital as per-trade max exposure
                self.max_exposure_usdt = max(sc_usdt * 0.5, 50.0)
            else:
                self.max_exposure_usdt = 200.0

        # Initialize order executor
        self.executor = OrderExecutor()

        # Event-driven scanning state
        self.updated_symbols: Set[str] = set()
        self.last_scan_time: Dict[str, float] = {}

        # ensure persistence file
        if not os.path.exists(self.persist_path):
            with open(self.persist_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["ts", "symbol", "buy_ex", "sell_ex", "qty", "buy_price", "sell_price", "net", "roi_pct"])

        self.recent_cache = {}
        
        logger.info(f"ArbitrageEngine initialized: min_roi={self.min_net_pct}%, max_exposure=${self.max_exposure_usdt}, safety_factor={self.safety_factor}")

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

        # BIDIRECTIONAL SCAN FIX: Check ALL directed pairs (A->B AND B->A)
        # Previous version only checked exchanges[i+1:] which missed 50% of opportunities
        for i, buy_ex in enumerate(exchanges):
            # Check this exchange as buy against ALL other exchanges as sell
            for j, sell_ex in enumerate(exchanges):
                if i == j:  # Skip same exchange
                    continue
                    
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

                # S1 PREFILTER: Quick top-of-book spread check before expensive simulation
                # Skip if gross spread is too small to be profitable after fees
                top_bid = bids[0][0]
                top_ask = asks[0][0]
                gross_spread_pct = ((top_bid - top_ask) / top_ask) * 100.0 if top_ask > 0 else 0
                
                buy_fee = self._fee_rate(buy_ex, "taker")
                sell_fee = self._fee_rate(sell_ex, "taker")
                sum_fees_pct = (buy_fee + sell_fee) * 100.0
                
                # Prefilter: skip if spread < 80% of fees (won't be profitable)
                if gross_spread_pct < sum_fees_pct * 0.8:
                    continue

                # choose qty adaptively
                buy_price_est = asks[0][0] if asks else None
                qty = self._choose_qty(asks, bids, buy_price_est)
                if qty <= 0:
                    continue

                # A5 RISK CHECK: Skip anomalous spreads (likely data errors)
                if gross_spread_pct > settings.ANOMALOUS_SPREAD_PCT:
                    logger.warning(f"Skipping anomalous spread {gross_spread_pct:.2f}% for {symbol} {buy_ex}->{sell_ex} (threshold: {settings.ANOMALOUS_SPREAD_PCT}%)")
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
        
        # Sort by net profit
        res.sort(key=lambda x: x["net"], reverse=True)
        
        # Limit to max concurrent opportunities
        if len(res) > settings.MAX_CONCURRENT_OPPORTUNITIES:
            logger.debug(f"Limiting to top {settings.MAX_CONCURRENT_OPPORTUNITIES} opportunities (found {len(res)})")
            res = res[:settings.MAX_CONCURRENT_OPPORTUNITIES]
        
        return res

    def mark_symbol_updated(self, symbol: str):
        """Mark a symbol as having updated data (for event-driven scanning)."""
        if settings.EVENT_DRIVEN_SCAN:
            self.updated_symbols.add(symbol)

    async def run(self, symbols: List[str]):
        """Main scanning loop with event-driven optimization."""
        logger.info(f"Starting arbitrage engine for {len(symbols)} symbols")
        last_stats_print = time.time()
        
        while True:
            scan_start = time.time()
            
            # Determine which symbols to scan
            if settings.EVENT_DRIVEN_SCAN and self.updated_symbols:
                # Only scan symbols that have been updated
                symbols_to_scan = list(self.updated_symbols)
                self.updated_symbols.clear()
            else:
                # Scan all symbols
                symbols_to_scan = symbols
            
            for s in symbols_to_scan:
                # Throttle per-symbol scanning
                last_scan = self.last_scan_time.get(s, 0)
                time_since_last = scan_start - last_scan
                if time_since_last < settings.MIN_SCAN_INTERVAL_PER_SYMBOL_SEC:
                    continue
                
                self.last_scan_time[s] = scan_start
                
                # Get market overview
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
                
                # Only log market data occasionally to reduce spam
                # Disabled by default - enable for debugging by changing condition to True
                if logger.isEnabledFor(logging.DEBUG) and False:
                    if best_bid[0] or best_ask[0]:
                        logger.debug(f"MARKET {s}: BEST_BID {best_bid[0] or '-'} {best_bid[1]} BEST_ASK {best_ask[0] or '-'} {best_ask[1]}")

                # Scan for opportunities
                opps = await self.scan_once(s)
                if opps:
                    for o in opps:
                        # Execute or log the opportunity
                        result = self.executor.execute_arbitrage(o)
                        
                        if result['status'] == 'simulated':
                            # Already logged by executor
                            pass
                        elif result['status'] == 'blocked':
                            logger.debug(f"Trade blocked: {result['reason']}")
                        elif result['status'] == 'error':
                            logger.error(f"Execution error: {result.get('reason', 'Unknown')}")
            
            # Print statistics periodically
            if time.time() - last_stats_print > 60.0:
                self.executor.print_statistics()
                last_stats_print = time.time()
            
            # Sleep based on configured interval
            await asyncio.sleep(settings.SCAN_INTERVAL_SEC)