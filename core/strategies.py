"""
All 14 trading strategies for the arbitrage bot.

Each strategy class implements:
  - name: human-readable strategy name
  - strategy_type: identifier for the strategy
  - async scan(store, symbols, exchanges, params) -> List[Dict]
    Returns a list of opportunity dicts compatible with OrderExecutor.execute_arbitrage()

Strategies are divided into:
  - FAST (run every scan cycle): CROSS_EXCHANGE, TRIANGULAR, SMART_ORDER, VOLATILITY
  - SLOW (run periodically): Grid, DCA, MarketMaking, Pairs, Funding, VolArb, Index, Spread, Momentum, Breakout
"""
import time
import math
import logging
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from .exchange_config import EXCHANGE_PARAMS
import settings

logger = logging.getLogger("strategies")


# ── Helper: simulate book execution ─────────────────────────────────────────
def _sim_book(levels: List[Tuple[float, float]], qty: float) -> Tuple[float, float]:
    """Walk order-book levels and return (avg_price, filled_qty)."""
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
    return cost / filled, filled


def _fee(exchange: str, side: str = "taker") -> float:
    p = EXCHANGE_PARAMS.get(exchange, {})
    return p.get(side, p.get("taker", 0.002))


def _mid_price(rec: dict) -> Optional[float]:
    b = rec.get("bid")
    a = rec.get("ask")
    if b and a:
        return (b + a) / 2.0
    return b or a or None


# ─────────────────────────────────────────────────────────────────────────────
# 1. CROSS_EXCHANGE  (already in ArbitrageEngine – extracted for dispatcher)
# ─────────────────────────────────────────────────────────────────────────────
class CrossExchangeStrategy:
    name = "CROSS_EXCHANGE"
    strategy_type = "CROSS_EXCHANGE"
    priority = 1.0  # highest priority

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """Delegated to ArbitrageEngine.scan_once – returns [] here to avoid duplication."""
        return []  # handled by engine.scan_once()


# ─────────────────────────────────────────────────────────────────────────────
# 2. TRIANGULAR – A→B→C→A within one exchange
# ─────────────────────────────────────────────────────────────────────────────
class TriangularStrategy:
    name = "TRIANGULAR"
    strategy_type = "TRIANGULAR"
    priority = 0.5

    # Pre-defined triangular routes using configured symbols
    ROUTES = [
        ("BTC-USDT", "ETH-BTC", "ETH-USDT"),
        ("BTC-USDT", "SOL-BTC", "SOL-USDT"),
        ("BTC-USDT", "XRP-BTC", "XRP-USDT"),
        ("BTC-USDT", "BNB-BTC", "BNB-USDT"),
        ("ETH-USDT", "SOL-ETH", "SOL-USDT"),
    ]

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        For each exchange, check triangular routes:
          Step 1: Buy B with A  (e.g. buy ETH with USDT)
          Step 2: Buy C with B  (e.g. buy BTC with ETH, via ETH-BTC)
          Step 3: Sell C for A  (e.g. sell BTC for USDT)
        If net > fees we have an opportunity.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for route in self.ROUTES:
            sym_ab, sym_bc, sym_ac = route
            for exchange in EXCHANGE_PARAMS:
                rec_ab = snap.get(sym_ab, {}).get(exchange)
                rec_bc = snap.get(sym_bc, {}).get(exchange)
                rec_ac = snap.get(sym_ac, {}).get(exchange)
                if not all([rec_ab, rec_bc, rec_ac]):
                    continue

                ask_ab = rec_ab.get("ask")  # buy AB
                ask_bc = rec_bc.get("ask")  # buy BC
                bid_ac = rec_ac.get("bid")  # sell AC

                bid_ab = rec_ab.get("bid")  # sell AB
                bid_bc = rec_bc.get("bid")  # sell BC
                ask_ac = rec_ac.get("ask")  # buy AC

                if not all([ask_ab, ask_bc, bid_ac, bid_ab, bid_bc, ask_ac]):
                    continue

                fee_rate = _fee(exchange)

                # Forward: USDT → A → B → USDT
                # Start with $1, buy A, trade A→B, sell B
                fwd = (1.0 / ask_ab) * bid_bc * bid_ac
                fwd_net = fwd * (1 - fee_rate) ** 3
                fwd_profit_pct = (fwd_net - 1.0) * 100

                if fwd_profit_pct >= min_roi:
                    qty_usdt = min(settings.MAX_EXPOSURE_USDT, 100.0)
                    net_usdt = qty_usdt * (fwd_net - 1.0)
                    results.append({
                        "symbol": f"{sym_ab}→{sym_bc}→{sym_ac}",
                        "buy_ex": exchange,
                        "sell_ex": exchange,
                        "qty": qty_usdt / ask_ab,
                        "buy_avg": ask_ab,
                        "sell_avg": bid_ac,
                        "gross": qty_usdt * (fwd - 1.0),
                        "fees": qty_usdt * (fwd - fwd_net),
                        "net": net_usdt,
                        "roi_pct": fwd_profit_pct,
                        "strategy": self.strategy_type,
                        "route": f"fwd:{sym_ab}→{sym_bc}→{sym_ac}",
                    })

                # Reverse: USDT → B → A → USDT
                rev = (1.0 / ask_ac) * (1.0 / ask_bc) * bid_ab
                rev_net = rev * (1 - fee_rate) ** 3
                rev_profit_pct = (rev_net - 1.0) * 100

                if rev_profit_pct >= min_roi:
                    qty_usdt = min(settings.MAX_EXPOSURE_USDT, 100.0)
                    net_usdt = qty_usdt * (rev_net - 1.0)
                    results.append({
                        "symbol": f"{sym_ac}→{sym_bc}→{sym_ab}",
                        "buy_ex": exchange,
                        "sell_ex": exchange,
                        "qty": qty_usdt / ask_ac,
                        "buy_avg": ask_ac,
                        "sell_avg": bid_ab,
                        "gross": qty_usdt * (rev - 1.0),
                        "fees": qty_usdt * (rev - rev_net),
                        "net": net_usdt,
                        "roi_pct": rev_profit_pct,
                        "strategy": self.strategy_type,
                        "route": f"rev:{sym_ac}→{sym_bc}→{sym_ab}",
                    })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 3. SMART_ORDER – choose order type (market/limit) based on spread width
# ─────────────────────────────────────────────────────────────────────────────
class SmartOrderStrategy:
    name = "SMART_ORDER"
    strategy_type = "SMART_ORDER"
    priority = 0.8

    # Thresholds for order type selection
    MARKET_THRESHOLD = 2.0   # spread > 2× fee → market order is safe
    LIMIT_THRESHOLD = 3.0    # spread > 3× fee → limit order for better fill

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        Analyze spread-to-fee ratio across exchanges for each symbol.
        When spread is wide enough, recommend optimal order type.
        Returns opportunities where smart order routing improves execution.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for symbol in symbols:
            exmap = snap.get(symbol, {})
            exchanges = list(exmap.keys())
            if len(exchanges) < 2:
                continue

            for buy_ex in exchanges:
                for sell_ex in exchanges:
                    if buy_ex == sell_ex:
                        continue
                    buy_rec = exmap.get(buy_ex, {})
                    sell_rec = exmap.get(sell_ex, {})
                    ask = buy_rec.get("ask")
                    bid = sell_rec.get("bid")
                    if not ask or not bid or bid <= ask:
                        continue

                    spread_pct = ((bid - ask) / ask) * 100
                    total_fee_pct = (_fee(buy_ex) + _fee(sell_ex)) * 100

                    if total_fee_pct == 0:
                        continue

                    ratio = spread_pct / total_fee_pct

                    if ratio >= self.MARKET_THRESHOLD:
                        # Determine order type
                        if ratio >= self.LIMIT_THRESHOLD:
                            order_type = "limit"
                            # Limit orders can capture maker rebate.
                            # NOTE: in live execution, limit orders may not fill
                            # immediately — treat this as optimistic; taker fees
                            # are the conservative baseline.
                            effective_fee = (_fee(buy_ex, "maker") + _fee(sell_ex, "maker")) * 100
                        else:
                            order_type = "market"
                            effective_fee = total_fee_pct

                        net_pct = spread_pct - effective_fee
                        if net_pct < min_roi:
                            continue

                        qty = settings.DEFAULT_QUANTITY
                        buy_cost = ask * qty
                        if buy_cost > settings.MAX_EXPOSURE_USDT:
                            qty = settings.MAX_EXPOSURE_USDT / ask

                        net_usdt = (bid - ask) * qty - (ask * qty * _fee(buy_ex) + bid * qty * _fee(sell_ex))

                        results.append({
                            "symbol": symbol,
                            "buy_ex": buy_ex,
                            "sell_ex": sell_ex,
                            "qty": qty,
                            "buy_avg": ask,
                            "sell_avg": bid,
                            "gross": (bid - ask) * qty,
                            "fees": (ask * qty * _fee(buy_ex) + bid * qty * _fee(sell_ex)),
                            "net": net_usdt,
                            "roi_pct": net_pct,
                            "strategy": self.strategy_type,
                            "order_type": order_type,
                            "spread_fee_ratio": ratio,
                        })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results[:settings.MAX_CONCURRENT_OPPORTUNITIES]


# ─────────────────────────────────────────────────────────────────────────────
# 4. VOLATILITY – exploit high-volatility symbols for wider spreads
# ─────────────────────────────────────────────────────────────────────────────
class VolatilityStrategy:
    name = "VOLATILITY"
    strategy_type = "VOLATILITY"
    priority = 0.3

    def __init__(self):
        self._price_history: Dict[str, List[float]] = defaultdict(list)
        self._max_history = 60  # keep last 60 price points

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        Track price volatility per symbol across exchanges.
        When a symbol becomes highly volatile (large recent moves),
        the cross-exchange spread tends to widen → opportunity.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for symbol in symbols:
            exmap = snap.get(symbol, {})
            if not exmap:
                continue

            # Collect mid prices across all exchanges
            mids = []
            for ex, rec in exmap.items():
                mid = _mid_price(rec)
                if mid:
                    mids.append((ex, mid))

            if len(mids) < 2:
                continue

            # Track price history
            avg_mid = sum(m for _, m in mids) / len(mids)
            history = self._price_history[symbol]
            history.append(avg_mid)
            if len(history) > self._max_history:
                history.pop(0)

            # Need at least 5 data points to assess volatility
            if len(history) < 5:
                continue

            # Calculate recent volatility (std dev of returns)
            returns = []
            for i in range(1, len(history)):
                if history[i - 1] > 0:
                    returns.append((history[i] - history[i - 1]) / history[i - 1])
            if not returns:
                continue

            volatility = (sum(r ** 2 for r in returns) / len(returns)) ** 0.5 * 100

            # High volatility → look for wider cross-exchange spreads
            if volatility < 0.01:  # less than 0.01% volatility → skip
                continue

            # Find best buy/sell across exchanges
            best_ask_ex, best_ask = min(mids, key=lambda x: x[1])
            best_bid_ex, best_bid = max(mids, key=lambda x: x[1])

            if best_bid_ex == best_ask_ex or best_bid <= best_ask:
                continue

            buy_rec = exmap.get(best_ask_ex, {})
            sell_rec = exmap.get(best_bid_ex, {})

            actual_ask = buy_rec.get("ask", best_ask)
            actual_bid = sell_rec.get("bid", best_bid)

            if actual_bid <= actual_ask:
                continue

            spread_pct = ((actual_bid - actual_ask) / actual_ask) * 100
            fee_pct = (_fee(best_ask_ex) + _fee(best_bid_ex)) * 100
            net_pct = spread_pct - fee_pct

            if net_pct < min_roi:
                continue

            qty = settings.DEFAULT_QUANTITY
            if actual_ask * qty > settings.MAX_EXPOSURE_USDT:
                qty = settings.MAX_EXPOSURE_USDT / actual_ask

            net_usdt = (actual_bid - actual_ask) * qty - (actual_ask * qty * _fee(best_ask_ex) + actual_bid * qty * _fee(best_bid_ex))

            results.append({
                "symbol": symbol,
                "buy_ex": best_ask_ex,
                "sell_ex": best_bid_ex,
                "qty": qty,
                "buy_avg": actual_ask,
                "sell_avg": actual_bid,
                "gross": (actual_bid - actual_ask) * qty,
                "fees": (actual_ask * qty * _fee(best_ask_ex) + actual_bid * qty * _fee(best_bid_ex)),
                "net": net_usdt,
                "roi_pct": net_pct,
                "strategy": self.strategy_type,
                "volatility_pct": volatility,
            })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 5. GRID TRADING – place buy/sell grids around the current price
# ─────────────────────────────────────────────────────────────────────────────
class GridTradingStrategy:
    name = "Grid Trading"
    strategy_type = "GRID"
    priority = 0.3

    def __init__(self):
        self.grid_levels = 5
        self.grid_spacing_pct = 0.1  # 0.1% between levels
        self._active_grids: Dict[str, Dict] = {}  # symbol -> grid state

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        For each symbol, define a grid of buy/sell levels around mid price.
        When the price crosses a grid level, generate a signal.
        In dry-run: simulate grid entries when price moves through levels.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for symbol in symbols:
            exmap = snap.get(symbol, {})
            if not exmap:
                continue

            # Get best prices across exchanges
            all_mids = []
            for ex, rec in exmap.items():
                mid = _mid_price(rec)
                if mid:
                    all_mids.append((ex, mid, rec))

            if not all_mids:
                continue

            avg_mid = sum(m for _, m, _ in all_mids) / len(all_mids)

            # Initialize or update grid
            if symbol not in self._active_grids:
                self._active_grids[symbol] = {
                    "center": avg_mid,
                    "last_price": avg_mid,
                    "levels_hit": set(),
                }

            grid = self._active_grids[symbol]
            last_price = grid["last_price"]

            # Generate grid levels
            for i in range(-self.grid_levels, self.grid_levels + 1):
                if i == 0:
                    continue
                level_price = grid["center"] * (1 + i * self.grid_spacing_pct / 100)
                level_key = f"{symbol}:{i}"

                # Check if price crossed this level
                if level_key in grid["levels_hit"]:
                    continue

                crossed = False
                if i > 0 and last_price < level_price <= avg_mid:
                    # Price rose through a sell level → sell signal
                    crossed = True
                    side = "sell"
                elif i < 0 and last_price > level_price >= avg_mid:
                    # Price fell through a buy level → buy signal
                    crossed = True
                    side = "buy"

                if crossed:
                    grid["levels_hit"].add(level_key)
                    # Find best exchange for this trade
                    if side == "buy":
                        best_ex, best_price, best_rec = min(all_mids, key=lambda x: x[1])
                        actual_price = best_rec.get("ask", best_price)
                    else:
                        best_ex, best_price, best_rec = max(all_mids, key=lambda x: x[1])
                        actual_price = best_rec.get("bid", best_price)

                    # Grid profit: distance from center to level
                    profit_per_unit = abs(level_price - grid["center"])
                    roi = (profit_per_unit / grid["center"]) * 100

                    if roi < min_roi:
                        continue

                    qty = settings.DEFAULT_QUANTITY
                    if actual_price * qty > settings.MAX_EXPOSURE_USDT:
                        qty = settings.MAX_EXPOSURE_USDT / actual_price

                    net = profit_per_unit * qty * (1 - _fee(best_ex) * 2)
                    if net <= 0:
                        continue

                    results.append({
                        "symbol": symbol,
                        "buy_ex": best_ex,
                        "sell_ex": best_ex,
                        "qty": qty,
                        "buy_avg": actual_price if side == "buy" else grid["center"],
                        "sell_avg": grid["center"] if side == "buy" else actual_price,
                        "gross": profit_per_unit * qty,
                        "fees": actual_price * qty * _fee(best_ex) * 2,
                        "net": net,
                        "roi_pct": roi,
                        "strategy": self.strategy_type,
                        "grid_side": side,
                        "grid_level": i,
                    })

            grid["last_price"] = avg_mid

            # Reset grid if price moved far from center
            if abs(avg_mid - grid["center"]) / grid["center"] > 0.01:  # >1% from center
                grid["center"] = avg_mid
                grid["levels_hit"].clear()

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 6. DCA – Dollar-Cost Averaging on price dips
# ─────────────────────────────────────────────────────────────────────────────
class DCAStrategy:
    name = "DCA Strategy"
    strategy_type = "DCA"
    priority = 0.2

    def __init__(self):
        self._price_sma: Dict[str, List[float]] = defaultdict(list)
        self._sma_window = 20
        self._dip_threshold_pct = 0.5  # price must be 0.5% below SMA

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        Track a simple moving average per symbol.
        When price dips below SMA by threshold → generate buy signal.
        Sell signal when price recovers above SMA.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for symbol in symbols:
            exmap = snap.get(symbol, {})
            if not exmap:
                continue

            # Average price across exchanges
            mids = [_mid_price(rec) for rec in exmap.values() if _mid_price(rec)]
            if not mids:
                continue
            current_price = sum(mids) / len(mids)

            # Update SMA
            history = self._price_sma[symbol]
            history.append(current_price)
            if len(history) > self._sma_window:
                history.pop(0)

            if len(history) < self._sma_window:
                continue

            sma = sum(history) / len(history)

            # DCA buy signal: price significantly below SMA
            dip_pct = ((sma - current_price) / sma) * 100
            if dip_pct >= self._dip_threshold_pct:
                # Find cheapest exchange to buy
                best_buy_ex = None
                best_ask = float("inf")
                for ex, rec in exmap.items():
                    ask = rec.get("ask")
                    if ask and ask < best_ask:
                        best_ask = ask
                        best_buy_ex = ex

                if not best_buy_ex:
                    continue

                # Expected profit: when price reverts to SMA
                expected_sell = sma
                net_pct = ((expected_sell - best_ask) / best_ask) * 100 - _fee(best_buy_ex) * 100 * 2

                if net_pct < min_roi:
                    continue

                qty = settings.DEFAULT_QUANTITY
                if best_ask * qty > settings.MAX_EXPOSURE_USDT:
                    qty = settings.MAX_EXPOSURE_USDT / best_ask

                net_usdt = (expected_sell - best_ask) * qty - best_ask * qty * _fee(best_buy_ex) * 2

                results.append({
                    "symbol": symbol,
                    "buy_ex": best_buy_ex,
                    "sell_ex": best_buy_ex,
                    "qty": qty,
                    "buy_avg": best_ask,
                    "sell_avg": expected_sell,
                    "gross": (expected_sell - best_ask) * qty,
                    "fees": best_ask * qty * _fee(best_buy_ex) * 2,
                    "net": net_usdt,
                    "roi_pct": net_pct,
                    "strategy": self.strategy_type,
                    "dip_pct": dip_pct,
                    "sma": sma,
                })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 7. MARKET MAKING – place bids/asks around mid price for spread capture
# ─────────────────────────────────────────────────────────────────────────────
class MarketMakingStrategy:
    name = "Market Making"
    strategy_type = "MARKET_MAKING"
    priority = 0.3

    def __init__(self):
        self.min_spread_pct = 0.1  # minimum spread to provide liquidity

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        For exchanges with wide spreads, identify market-making opportunities
        where placing a bid above the best bid and ask below the best ask
        could capture the spread.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for symbol in symbols:
            exmap = snap.get(symbol, {})

            for ex, rec in exmap.items():
                bid = rec.get("bid")
                ask = rec.get("ask")
                if not bid or not ask or ask <= bid:
                    continue

                spread_pct = ((ask - bid) / bid) * 100
                maker_fee = _fee(ex, "maker")
                total_fee_pct = maker_fee * 2 * 100

                net_spread = spread_pct - total_fee_pct
                if net_spread < self.min_spread_pct or net_spread < min_roi:
                    continue

                mid = (bid + ask) / 2
                # Place bid slightly above best bid, ask slightly below best ask
                our_bid = bid + (mid - bid) * 0.1  # 10% into the spread
                our_ask = ask - (ask - mid) * 0.1

                qty = settings.DEFAULT_QUANTITY
                if our_ask * qty > settings.MAX_EXPOSURE_USDT:
                    qty = settings.MAX_EXPOSURE_USDT / our_ask

                gross = (our_ask - our_bid) * qty
                fees = (our_bid * qty * maker_fee + our_ask * qty * maker_fee)
                net = gross - fees
                roi = ((our_ask - our_bid) / our_bid - maker_fee * 2) * 100

                if net <= 0 or roi < min_roi:
                    continue

                results.append({
                    "symbol": symbol,
                    "buy_ex": ex,
                    "sell_ex": ex,
                    "qty": qty,
                    "buy_avg": our_bid,
                    "sell_avg": our_ask,
                    "gross": gross,
                    "fees": fees,
                    "net": net,
                    "roi_pct": roi,
                    "strategy": self.strategy_type,
                    "exchange_spread_pct": spread_pct,
                })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 8. PAIRS TRADING – trade correlated pairs (mean reversion)
# ─────────────────────────────────────────────────────────────────────────────
class PairsTradingStrategy:
    name = "Pairs Trading"
    strategy_type = "PAIRS"
    priority = 0.3

    # Naturally correlated crypto pairs
    PAIRS = [
        ("BTC-USDT", "ETH-USDT"),
        ("ETH-USDT", "SOL-USDT"),
        ("BNB-USDT", "ETH-USDT"),
        ("LTC-USDT", "BTC-USDT"),
        ("ADA-USDT", "DOT-USDT"),
    ]

    def __init__(self):
        self._ratio_history: Dict[str, List[float]] = defaultdict(list)
        self._history_window = 30
        self._z_threshold = 2.0  # standard deviations for signal

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        Track the price ratio between correlated pairs.
        When the ratio deviates from its mean by > z_threshold standard deviations,
        trade on mean reversion (buy the cheap one, sell the expensive one).
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for sym_a, sym_b in self.PAIRS:
            if sym_a not in symbols or sym_b not in symbols:
                continue

            exmap_a = snap.get(sym_a, {})
            exmap_b = snap.get(sym_b, {})
            if not exmap_a or not exmap_b:
                continue

            # Get average mid prices
            mids_a = [_mid_price(rec) for rec in exmap_a.values() if _mid_price(rec)]
            mids_b = [_mid_price(rec) for rec in exmap_b.values() if _mid_price(rec)]
            if not mids_a or not mids_b:
                continue

            price_a = sum(mids_a) / len(mids_a)
            price_b = sum(mids_b) / len(mids_b)

            if price_b == 0:
                continue

            ratio = price_a / price_b
            pair_key = f"{sym_a}/{sym_b}"

            # Track ratio history
            history = self._ratio_history[pair_key]
            history.append(ratio)
            if len(history) > self._history_window:
                history.pop(0)

            if len(history) < self._history_window:
                continue

            mean_ratio = sum(history) / len(history)
            variance = sum((r - mean_ratio) ** 2 for r in history) / len(history)
            std_dev = variance ** 0.5

            if std_dev == 0:
                continue

            z_score = (ratio - mean_ratio) / std_dev

            if abs(z_score) < self._z_threshold:
                continue

            # z > threshold: ratio too high → A is overpriced relative to B
            # → sell A, buy B (expect reversion)
            if z_score > self._z_threshold:
                # Sell A, Buy B
                sell_sym, buy_sym = sym_a, sym_b
                sell_price = price_a
                buy_price = price_b
                sell_exmap = exmap_a
                buy_exmap = exmap_b
            else:
                # Buy A, Sell B
                buy_sym, sell_sym = sym_a, sym_b
                buy_price = price_a
                sell_price = price_b
                buy_exmap = exmap_a
                sell_exmap = exmap_b

            # Find best exchanges
            best_buy_ex = min(buy_exmap, key=lambda ex: buy_exmap[ex].get("ask", float("inf")))
            best_sell_ex = max(sell_exmap, key=lambda ex: sell_exmap[ex].get("bid", 0))

            actual_buy = buy_exmap[best_buy_ex].get("ask", buy_price)
            actual_sell = sell_exmap[best_sell_ex].get("bid", sell_price)

            # Expected reversion profit
            expected_move_pct = abs(z_score - 1.0) * std_dev / mean_ratio * 100
            net_pct = expected_move_pct - (_fee(best_buy_ex) + _fee(best_sell_ex)) * 100

            if net_pct < min_roi:
                continue

            qty = settings.DEFAULT_QUANTITY
            if actual_buy * qty > settings.MAX_EXPOSURE_USDT:
                qty = settings.MAX_EXPOSURE_USDT / actual_buy

            gross = actual_buy * qty * expected_move_pct / 100
            fees = actual_buy * qty * (_fee(best_buy_ex) + _fee(best_sell_ex))
            net_usdt = gross - fees

            results.append({
                "symbol": f"{buy_sym}↔{sell_sym}",
                "buy_ex": best_buy_ex,
                "sell_ex": best_sell_ex,
                "qty": qty,
                "buy_avg": actual_buy,
                "sell_avg": actual_sell,
                "gross": gross,
                "fees": fees,
                "net": net_usdt,
                "roi_pct": net_pct,
                "strategy": self.strategy_type,
                "z_score": z_score,
                "pair": pair_key,
            })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 9. FUNDING RATE – exploit funding rate differences across exchanges
# ─────────────────────────────────────────────────────────────────────────────
class FundingRateStrategy:
    name = "Enhanced Funding Rate"
    strategy_type = "FUNDING"
    priority = 0.2

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        Compare prices across exchanges to infer funding rate pressure.
        When one exchange trades at a significant premium/discount,
        the funding rate should push price back → trade the convergence.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for symbol in symbols:
            exmap = snap.get(symbol, {})
            if len(exmap) < 2:
                continue

            prices = {}
            for ex, rec in exmap.items():
                mid = _mid_price(rec)
                if mid:
                    prices[ex] = mid

            if len(prices) < 2:
                continue

            avg_price = sum(prices.values()) / len(prices)
            if avg_price == 0:
                continue

            # Find exchanges trading at premium/discount
            for ex, price in prices.items():
                deviation_pct = ((price - avg_price) / avg_price) * 100

                # Premium > 0.1%: expect price to come down → sell on this exchange
                # Discount < -0.1%: expect price to come up → buy on this exchange
                if abs(deviation_pct) < 0.1:
                    continue

                if deviation_pct > 0:
                    # Premium → sell here, buy on cheapest exchange
                    cheapest_ex = min(prices, key=prices.get)
                    if cheapest_ex == ex:
                        continue
                    buy_price = exmap[cheapest_ex].get("ask", prices[cheapest_ex])
                    sell_price = exmap[ex].get("bid", price)
                else:
                    # Discount → buy here, sell on most expensive exchange
                    expensive_ex = max(prices, key=prices.get)
                    if expensive_ex == ex:
                        continue
                    buy_price = exmap[ex].get("ask", price)
                    sell_price = exmap[expensive_ex].get("bid", prices[expensive_ex])
                    cheapest_ex = ex
                    ex = expensive_ex

                if sell_price <= buy_price:
                    continue

                spread_pct = ((sell_price - buy_price) / buy_price) * 100
                fee_pct = (_fee(cheapest_ex) + _fee(ex)) * 100
                net_pct = spread_pct - fee_pct

                if net_pct < min_roi:
                    continue

                qty = settings.DEFAULT_QUANTITY
                if buy_price * qty > settings.MAX_EXPOSURE_USDT:
                    qty = settings.MAX_EXPOSURE_USDT / buy_price

                net_usdt = (sell_price - buy_price) * qty - buy_price * qty * (_fee(cheapest_ex) + _fee(ex))

                results.append({
                    "symbol": symbol,
                    "buy_ex": cheapest_ex,
                    "sell_ex": ex,
                    "qty": qty,
                    "buy_avg": buy_price,
                    "sell_avg": sell_price,
                    "gross": (sell_price - buy_price) * qty,
                    "fees": buy_price * qty * (_fee(cheapest_ex) + _fee(ex)),
                    "net": net_usdt,
                    "roi_pct": net_pct,
                    "strategy": self.strategy_type,
                    "deviation_pct": deviation_pct,
                })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 10. VOLATILITY ARBITRAGE – exploit volatility differences across exchanges
# ─────────────────────────────────────────────────────────────────────────────
class VolatilityArbStrategy:
    name = "Volatility Arbitrage"
    strategy_type = "VOL_ARB"
    priority = 0.2

    def __init__(self):
        self._spread_history: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        self._window = 20

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        Track spread (ask-bid) per exchange per symbol.
        When one exchange's spread widens significantly vs others,
        the exchange with the narrow spread is more efficiently priced.
        Trade the difference.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for symbol in symbols:
            exmap = snap.get(symbol, {})
            if len(exmap) < 2:
                continue

            spreads = {}
            for ex, rec in exmap.items():
                bid = rec.get("bid")
                ask = rec.get("ask")
                if bid and ask and ask > bid:
                    spread_pct = ((ask - bid) / bid) * 100
                    spreads[ex] = spread_pct

                    # Track history
                    self._spread_history[symbol][ex].append(spread_pct)
                    if len(self._spread_history[symbol][ex]) > self._window:
                        self._spread_history[symbol][ex].pop(0)

            if len(spreads) < 2:
                continue

            # Compare spreads: exchange with much wider spread is less efficient
            avg_spread = sum(spreads.values()) / len(spreads)
            for wide_ex, wide_spread in spreads.items():
                for narrow_ex, narrow_spread in spreads.items():
                    if wide_ex == narrow_ex:
                        continue
                    if wide_spread < narrow_spread * 1.5:  # need 50% wider
                        continue

                    # The wide-spread exchange likely has a distorted price
                    wide_rec = exmap[wide_ex]
                    narrow_rec = exmap[narrow_ex]

                    # Buy on narrow-spread exchange (better price), sell on wide-spread
                    buy_price = narrow_rec.get("ask", 0)
                    sell_price = wide_rec.get("bid", 0)

                    if not buy_price or not sell_price or sell_price <= buy_price:
                        continue

                    spread_diff = ((sell_price - buy_price) / buy_price) * 100
                    fee_pct = (_fee(narrow_ex) + _fee(wide_ex)) * 100
                    net_pct = spread_diff - fee_pct

                    if net_pct < min_roi:
                        continue

                    qty = settings.DEFAULT_QUANTITY
                    if buy_price * qty > settings.MAX_EXPOSURE_USDT:
                        qty = settings.MAX_EXPOSURE_USDT / buy_price

                    net_usdt = (sell_price - buy_price) * qty - buy_price * qty * (_fee(narrow_ex) + _fee(wide_ex))

                    results.append({
                        "symbol": symbol,
                        "buy_ex": narrow_ex,
                        "sell_ex": wide_ex,
                        "qty": qty,
                        "buy_avg": buy_price,
                        "sell_avg": sell_price,
                        "gross": (sell_price - buy_price) * qty,
                        "fees": buy_price * qty * (_fee(narrow_ex) + _fee(wide_ex)),
                        "net": net_usdt,
                        "roi_pct": net_pct,
                        "strategy": self.strategy_type,
                        "spread_ratio": wide_spread / narrow_spread if narrow_spread else 0,
                    })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results[:settings.MAX_CONCURRENT_OPPORTUNITIES]


# ─────────────────────────────────────────────────────────────────────────────
# 11. INDEX ARBITRAGE – trade spot vs composite index price
# ─────────────────────────────────────────────────────────────────────────────
class IndexArbStrategy:
    name = "Index Arbitrage"
    strategy_type = "INDEX_ARB"
    priority = 0.2

    # Composite index: weighted basket of top coins
    INDEX_WEIGHTS = {
        "BTC-USDT": 0.40,
        "ETH-USDT": 0.30,
        "SOL-USDT": 0.10,
        "BNB-USDT": 0.10,
        "XRP-USDT": 0.10,
    }

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        Compute a synthetic index from top-5 coins.
        For each component, compare its exchange-average price to its
        index-implied fair value.
        If a component trades at premium/discount vs the index → trade it.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        # Compute index value
        component_prices = {}
        for sym, weight in self.INDEX_WEIGHTS.items():
            exmap = snap.get(sym, {})
            mids = [_mid_price(rec) for rec in exmap.values() if _mid_price(rec)]
            if mids:
                component_prices[sym] = sum(mids) / len(mids)

        if len(component_prices) < 3:
            return results

        # Normalize index to 100
        index_value = sum(
            component_prices.get(sym, 0) * weight
            for sym, weight in self.INDEX_WEIGHTS.items()
        )
        if index_value == 0:
            return results

        # For each component, check deviation from index-implied price
        for sym, weight in self.INDEX_WEIGHTS.items():
            if sym not in component_prices:
                continue

            actual_price = component_prices[sym]
            # Fair value: if index = 100, then component should be index * weight / actual_weight
            # Simplified: compare per-exchange prices to the average
            exmap = snap.get(sym, {})

            for ex, rec in exmap.items():
                mid = _mid_price(rec)
                if not mid:
                    continue

                deviation_pct = ((mid - actual_price) / actual_price) * 100

                if abs(deviation_pct) < 0.1:
                    continue

                if deviation_pct > 0:
                    # Overpriced on this exchange → sell
                    sell_price = rec.get("bid", mid)
                    # Buy on cheapest exchange
                    cheapest_ex = None
                    cheapest_ask = float("inf")
                    for other_ex, other_rec in exmap.items():
                        if other_ex == ex:
                            continue
                        other_ask = other_rec.get("ask")
                        if other_ask and other_ask < cheapest_ask:
                            cheapest_ask = other_ask
                            cheapest_ex = other_ex

                    if not cheapest_ex or sell_price <= cheapest_ask:
                        continue

                    buy_price = cheapest_ask
                    buy_ex = cheapest_ex
                    sell_ex = ex
                else:
                    # Underpriced → buy on this exchange
                    buy_price = rec.get("ask", mid)
                    # Sell on most expensive exchange
                    expensive_ex = None
                    highest_bid = 0
                    for other_ex, other_rec in exmap.items():
                        if other_ex == ex:
                            continue
                        other_bid = other_rec.get("bid")
                        if other_bid and other_bid > highest_bid:
                            highest_bid = other_bid
                            expensive_ex = other_ex

                    if not expensive_ex or highest_bid <= buy_price:
                        continue

                    sell_price = highest_bid
                    buy_ex = ex
                    sell_ex = expensive_ex

                spread_pct = ((sell_price - buy_price) / buy_price) * 100
                fee_pct = (_fee(buy_ex) + _fee(sell_ex)) * 100
                net_pct = spread_pct - fee_pct

                if net_pct < min_roi:
                    continue

                qty = settings.DEFAULT_QUANTITY
                if buy_price * qty > settings.MAX_EXPOSURE_USDT:
                    qty = settings.MAX_EXPOSURE_USDT / buy_price

                net_usdt = (sell_price - buy_price) * qty - buy_price * qty * (_fee(buy_ex) + _fee(sell_ex))

                results.append({
                    "symbol": sym,
                    "buy_ex": buy_ex,
                    "sell_ex": sell_ex,
                    "qty": qty,
                    "buy_avg": buy_price,
                    "sell_avg": sell_price,
                    "gross": (sell_price - buy_price) * qty,
                    "fees": buy_price * qty * (_fee(buy_ex) + _fee(sell_ex)),
                    "net": net_usdt,
                    "roi_pct": net_pct,
                    "strategy": self.strategy_type,
                    "index_deviation_pct": deviation_pct,
                })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 12. SPREAD BETTING – trade on spread widening/narrowing between exchanges
# ─────────────────────────────────────────────────────────────────────────────
class SpreadBettingStrategy:
    name = "Spread Betting"
    strategy_type = "SPREAD"
    priority = 0.2

    def __init__(self):
        self._spread_history: Dict[str, List[float]] = defaultdict(list)
        self._window = 30

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        Track the bid-ask spread between two exchanges for each symbol.
        When the cross-exchange spread is historically wide → expect narrowing → trade.
        When historically narrow → expect widening → wait.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for symbol in symbols:
            exmap = snap.get(symbol, {})
            exchanges = list(exmap.keys())
            if len(exchanges) < 2:
                continue

            for i, ex_a in enumerate(exchanges):
                for ex_b in exchanges[i + 1:]:
                    rec_a = exmap[ex_a]
                    rec_b = exmap[ex_b]

                    mid_a = _mid_price(rec_a)
                    mid_b = _mid_price(rec_b)
                    if not mid_a or not mid_b:
                        continue

                    # Cross-exchange spread as percentage
                    cross_spread = abs(mid_a - mid_b) / min(mid_a, mid_b) * 100
                    pair_key = f"{symbol}:{ex_a}-{ex_b}"

                    self._spread_history[pair_key].append(cross_spread)
                    if len(self._spread_history[pair_key]) > self._window:
                        self._spread_history[pair_key].pop(0)

                    history = self._spread_history[pair_key]
                    if len(history) < 10:
                        continue

                    mean_spread = sum(history) / len(history)
                    std_spread = (sum((s - mean_spread) ** 2 for s in history) / len(history)) ** 0.5

                    if std_spread == 0:
                        continue

                    z = (cross_spread - mean_spread) / std_spread

                    # Spread is unusually wide → expect narrowing → trade the convergence
                    if z < 1.5:
                        continue

                    # Buy on cheaper exchange, sell on more expensive
                    if mid_a < mid_b:
                        buy_ex, sell_ex = ex_a, ex_b
                        buy_price = rec_a.get("ask", mid_a)
                        sell_price = rec_b.get("bid", mid_b)
                    else:
                        buy_ex, sell_ex = ex_b, ex_a
                        buy_price = rec_b.get("ask", mid_b)
                        sell_price = rec_a.get("bid", mid_a)

                    if sell_price <= buy_price:
                        continue

                    spread_pct = ((sell_price - buy_price) / buy_price) * 100
                    fee_pct = (_fee(buy_ex) + _fee(sell_ex)) * 100
                    net_pct = spread_pct - fee_pct

                    if net_pct < min_roi:
                        continue

                    qty = settings.DEFAULT_QUANTITY
                    if buy_price * qty > settings.MAX_EXPOSURE_USDT:
                        qty = settings.MAX_EXPOSURE_USDT / buy_price

                    net_usdt = (sell_price - buy_price) * qty - buy_price * qty * (_fee(buy_ex) + _fee(sell_ex))

                    results.append({
                        "symbol": symbol,
                        "buy_ex": buy_ex,
                        "sell_ex": sell_ex,
                        "qty": qty,
                        "buy_avg": buy_price,
                        "sell_avg": sell_price,
                        "gross": (sell_price - buy_price) * qty,
                        "fees": buy_price * qty * (_fee(buy_ex) + _fee(sell_ex)),
                        "net": net_usdt,
                        "roi_pct": net_pct,
                        "strategy": self.strategy_type,
                        "spread_z_score": z,
                    })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 13. MOMENTUM – follow price momentum with confirmation
# ─────────────────────────────────────────────────────────────────────────────
class MomentumStrategy:
    name = "Momentum Strategy"
    strategy_type = "MOMENTUM"
    priority = 0.2

    def __init__(self):
        self._price_history: Dict[str, List[float]] = defaultdict(list)
        self._window = 10
        self._momentum_threshold = 0.3  # 0.3% consistent move

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        Track short-term price momentum per symbol.
        When price has been consistently rising/falling across multiple exchanges,
        follow the trend by buying the cross-exchange dip (lagging exchange).
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for symbol in symbols:
            exmap = snap.get(symbol, {})
            if not exmap:
                continue

            mids = [_mid_price(rec) for rec in exmap.values() if _mid_price(rec)]
            if not mids:
                continue

            current_price = sum(mids) / len(mids)
            history = self._price_history[symbol]
            history.append(current_price)
            if len(history) > self._window:
                history.pop(0)

            if len(history) < self._window:
                continue

            # Calculate momentum: average of recent returns
            returns = []
            for i in range(1, len(history)):
                if history[i - 1] > 0:
                    returns.append((history[i] - history[i - 1]) / history[i - 1] * 100)

            if not returns:
                continue

            momentum = sum(returns) / len(returns)

            if abs(momentum) < self._momentum_threshold:
                continue

            # Strong momentum detected
            # Find the lagging exchange (cheapest if uptrend, most expensive if downtrend)
            exchange_prices = [(ex, _mid_price(rec)) for ex, rec in exmap.items() if _mid_price(rec)]
            if len(exchange_prices) < 2:
                continue

            if momentum > 0:
                # Uptrend: buy on the cheapest exchange (lagging), sell on most expensive
                buy_ex, _ = min(exchange_prices, key=lambda x: x[1])
                sell_ex, _ = max(exchange_prices, key=lambda x: x[1])
            else:
                # Downtrend: sell on the most expensive (lagging), buy on cheapest
                sell_ex, _ = max(exchange_prices, key=lambda x: x[1])
                buy_ex, _ = min(exchange_prices, key=lambda x: x[1])

            buy_price = exmap[buy_ex].get("ask", 0)
            sell_price = exmap[sell_ex].get("bid", 0)

            if not buy_price or not sell_price or sell_price <= buy_price:
                continue

            spread_pct = ((sell_price - buy_price) / buy_price) * 100
            fee_pct = (_fee(buy_ex) + _fee(sell_ex)) * 100
            net_pct = spread_pct - fee_pct

            if net_pct < min_roi:
                continue

            qty = settings.DEFAULT_QUANTITY
            if buy_price * qty > settings.MAX_EXPOSURE_USDT:
                qty = settings.MAX_EXPOSURE_USDT / buy_price

            net_usdt = (sell_price - buy_price) * qty - buy_price * qty * (_fee(buy_ex) + _fee(sell_ex))

            results.append({
                "symbol": symbol,
                "buy_ex": buy_ex,
                "sell_ex": sell_ex,
                "qty": qty,
                "buy_avg": buy_price,
                "sell_avg": sell_price,
                "gross": (sell_price - buy_price) * qty,
                "fees": buy_price * qty * (_fee(buy_ex) + _fee(sell_ex)),
                "net": net_usdt,
                "roi_pct": net_pct,
                "strategy": self.strategy_type,
                "momentum_pct": momentum,
            })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 14. BREAKOUT – detect and trade price breakouts from ranges
# ─────────────────────────────────────────────────────────────────────────────
class BreakoutStrategy:
    name = "Breakout Strategy"
    strategy_type = "BREAKOUT"
    priority = 0.2

    def __init__(self):
        self._price_ranges: Dict[str, Dict] = {}
        self._range_window = 30
        self._breakout_threshold = 0.5  # 0.5% above/below range

    async def scan(self, store, symbols, **kw) -> List[Dict]:
        """
        Track high/low price ranges per symbol.
        When price breaks above the range → upside breakout → buy the lagging exchange.
        When price breaks below → downside breakout → sell on the lagging exchange.
        """
        snap = store.snapshot()
        results = []
        min_roi = kw.get("min_net_pct", settings.MIN_NET_ROI_PCT)

        for symbol in symbols:
            exmap = snap.get(symbol, {})
            if not exmap:
                continue

            mids = [_mid_price(rec) for rec in exmap.values() if _mid_price(rec)]
            if not mids:
                continue

            current_price = sum(mids) / len(mids)

            # Track price range
            if symbol not in self._price_ranges:
                self._price_ranges[symbol] = {
                    "highs": [],
                    "lows": [],
                }

            ranges = self._price_ranges[symbol]
            ranges["highs"].append(current_price)
            ranges["lows"].append(current_price)
            if len(ranges["highs"]) > self._range_window:
                ranges["highs"].pop(0)
            if len(ranges["lows"]) > self._range_window:
                ranges["lows"].pop(0)

            if len(ranges["highs"]) < self._range_window:
                continue

            range_high = max(ranges["highs"][:-1])  # exclude current
            range_low = min(ranges["lows"][:-1])

            if range_high == 0 or range_low == 0:
                continue

            range_width = range_high - range_low
            if range_width == 0:
                continue

            # Check for breakout
            breakout_up = current_price > range_high * (1 + self._breakout_threshold / 100)
            breakout_down = current_price < range_low * (1 - self._breakout_threshold / 100)

            if not breakout_up and not breakout_down:
                continue

            # Find the lagging exchange
            exchange_prices = [(ex, _mid_price(rec)) for ex, rec in exmap.items() if _mid_price(rec)]
            if len(exchange_prices) < 2:
                continue

            if breakout_up:
                # Upside breakout: buy on cheapest (lagging) exchange
                buy_ex, _ = min(exchange_prices, key=lambda x: x[1])
                sell_ex, _ = max(exchange_prices, key=lambda x: x[1])
            else:
                # Downside breakout: sell on most expensive (lagging)
                sell_ex, _ = max(exchange_prices, key=lambda x: x[1])
                buy_ex, _ = min(exchange_prices, key=lambda x: x[1])

            buy_price = exmap[buy_ex].get("ask", 0)
            sell_price = exmap[sell_ex].get("bid", 0)

            if not buy_price or not sell_price or sell_price <= buy_price:
                continue

            spread_pct = ((sell_price - buy_price) / buy_price) * 100
            fee_pct = (_fee(buy_ex) + _fee(sell_ex)) * 100
            net_pct = spread_pct - fee_pct

            if net_pct < min_roi:
                continue

            qty = settings.DEFAULT_QUANTITY
            if buy_price * qty > settings.MAX_EXPOSURE_USDT:
                qty = settings.MAX_EXPOSURE_USDT / buy_price

            net_usdt = (sell_price - buy_price) * qty - buy_price * qty * (_fee(buy_ex) + _fee(sell_ex))

            results.append({
                "symbol": symbol,
                "buy_ex": buy_ex,
                "sell_ex": sell_ex,
                "qty": qty,
                "buy_avg": buy_price,
                "sell_avg": sell_price,
                "gross": (sell_price - buy_price) * qty,
                "fees": buy_price * qty * (_fee(buy_ex) + _fee(sell_ex)),
                "net": net_usdt,
                "roi_pct": net_pct,
                "strategy": self.strategy_type,
                "breakout_direction": "UP" if breakout_up else "DOWN",
                "range_high": range_high,
                "range_low": range_low,
            })

        results.sort(key=lambda x: x["net"], reverse=True)
        return results


# ─────────────────────────────────────────────────────────────────────────────
# Registry of all strategies
# ─────────────────────────────────────────────────────────────────────────────
ALL_STRATEGIES = [
    CrossExchangeStrategy(),    # 1
    TriangularStrategy(),       # 2
    SmartOrderStrategy(),       # 3
    VolatilityStrategy(),       # 4
    GridTradingStrategy(),      # 5
    DCAStrategy(),              # 6
    MarketMakingStrategy(),     # 7
    PairsTradingStrategy(),     # 8
    FundingRateStrategy(),      # 9
    VolatilityArbStrategy(),    # 10
    IndexArbStrategy(),         # 11
    SpreadBettingStrategy(),    # 12
    MomentumStrategy(),         # 13
    BreakoutStrategy(),         # 14
]

FAST_STRATEGIES = [s for s in ALL_STRATEGIES if s.priority >= 0.5]
SLOW_STRATEGIES = [s for s in ALL_STRATEGIES if s.priority < 0.5]
