"""
Strategy Dispatcher - Manages all 14 trading strategies

This module implements a two-tier scanning system:
- Fast strategies (0.15s): Arbitrage strategies that need speed
- Slow strategies (5 min): Position strategies that need time

Each slow strategy uses PriceStore data to analyze market conditions
and generate trading signals without requiring exchange API calls.
"""

import asyncio
import logging
import time
from collections import deque
from typing import Dict, List, Any, Optional

import settings

logger = logging.getLogger(__name__)


class StrategyDispatcher:
    """
    Dispatcher for all 14 trading strategies.
    Manages fast (arbitrage) and slow (position) strategy scanning.
    
    Uses PriceStore data to feed analysis into each strategy, allowing
    them to generate signals in both dry-run and live modes.
    """
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
        self.last_slow_scan = 0
        self.slow_scan_interval = 60  # 1 minute
        
        # Price history for strategies that need time series
        # symbol -> deque of (timestamp, mid_price)
        self._price_history: Dict[str, deque] = {}
        self._max_history = 200  # Keep 200 data points per symbol
        
        # Active signals: symbol → set of strategy names with recent signals
        # Used to attribute engine trades to strategies that signaled the same symbol
        self._active_signals: Dict[str, Dict[str, float]] = {}  # symbol → {strategy: timestamp}
        self._signal_ttl = 30.0  # Signal expires after 30 seconds
        
        # Strategy performance tracking
        self.strategy_stats = {
            'CROSS_EXCHANGE': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'TRIANGULAR': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'SMART_ORDER': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'VOLATILITY': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'GRID_TRADING': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'DCA': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'MARKET_MAKING': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'PAIRS_TRADING': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'FUNDING_RATE': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'VOLATILITY_ARB': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'INDEX_ARB': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'SPREAD_BETTING': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'MOMENTUM': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
            'BREAKOUT': {'calls': 0, 'opportunities': 0, 'signals': 0, 'trades': 0},
        }
        
        fast_names = ['CROSS_EXCHANGE', 'TRIANGULAR', 'SMART_ORDER', 'VOLATILITY']
        slow_names = [k for k in self.strategy_stats if k not in fast_names]
        logger.info(f"✅ StrategyDispatcher initialized with {len(self.strategy_stats)} strategies")
        logger.info(f"   Fast strategies ({len(fast_names)}): {', '.join(fast_names)}")
        logger.info(f"   Slow strategies ({len(slow_names)}): {', '.join(slow_names)}")
    
    def _get_price_store(self):
        """Get the PriceStore from bot_manager."""
        # IntegratedArbitrageBot uses 'store', other contexts may use 'price_store'
        return getattr(self.bot_manager, 'store', None) or getattr(self.bot_manager, 'price_store', None)
    
    def _get_mid_price(self, symbol: str, exchange: str = None) -> Optional[float]:
        """Get mid price for a symbol from PriceStore."""
        store = self._get_price_store()
        if not store:
            return None
        snap = store.snapshot()
        exmap = snap.get(symbol, {})
        if not exmap:
            return None
        
        if exchange and exchange in exmap:
            rec = exmap[exchange]
        else:
            # Use first available exchange
            rec = next(iter(exmap.values()))
        
        bid = rec.get("bid")
        ask = rec.get("ask")
        if bid and ask:
            return (bid + ask) / 2
        return bid or ask
    
    def _get_spread(self, symbol: str, exchange: str = None) -> Optional[float]:
        """Get bid-ask spread for a symbol."""
        store = self._get_price_store()
        if not store:
            return None
        snap = store.snapshot()
        exmap = snap.get(symbol, {})
        if not exmap:
            return None
        
        if exchange and exchange in exmap:
            rec = exmap[exchange]
        else:
            rec = next(iter(exmap.values()))
        
        bid = rec.get("bid")
        ask = rec.get("ask")
        if bid and ask and ask > 0:
            return (ask - bid) / ask
        return None
    
    def _update_price_history(self):
        """Update internal price history from PriceStore snapshots."""
        store = self._get_price_store()
        if not store:
            return
        
        snap = store.snapshot()
        now = time.time()
        
        for symbol, exmap in snap.items():
            if symbol not in self._price_history:
                self._price_history[symbol] = deque(maxlen=self._max_history)
            
            # Get first valid mid price across exchanges
            best_mid = None
            for ex, rec in exmap.items():
                bid = rec.get("bid")
                ask = rec.get("ask")
                if bid and ask:
                    best_mid = (bid + ask) / 2
                    break  # Use first valid price
            
            if best_mid:
                history = self._price_history[symbol]
                # Avoid duplicate timestamps (only add if > 1s since last)
                if not history or (now - history[-1][0]) >= 1.0:
                    history.append((now, best_mid))
    
    def _get_prices_list(self, symbol: str) -> List[float]:
        """Get price history as a simple list of prices."""
        history = self._price_history.get(symbol, deque())
        return [price for _, price in history]
    
    def record_engine_opportunities(self, count: int):
        """Called by main loop to feed ArbitrageEngine results into stats."""
        self.strategy_stats['CROSS_EXCHANGE']['opportunities'] += count
        if count > 0:
            self.strategy_stats['CROSS_EXCHANGE']['signals'] += count

    def record_engine_near_misses(self, count: int):
        """Called by main loop to feed ArbitrageEngine near-misses as signals."""
        if count > 0:
            self.strategy_stats['CROSS_EXCHANGE']['signals'] += count

    def record_signal(self, strategy_name: str, symbol: str):
        """Record that a strategy generated a signal for a symbol.
        
        Used for trade attribution: when the engine trades a symbol that
        a strategy recently signaled, the trade counts for that strategy too.
        """
        if symbol not in self._active_signals:
            self._active_signals[symbol] = {}
        self._active_signals[symbol][strategy_name] = time.time()

    def record_engine_trade(self, strategy_name: str = 'CROSS_EXCHANGE', symbol: str = ''):
        """Called by ArbitrageEngine when a trade is executed.
        
        Updates dashboard Trds column for CROSS_EXCHANGE and also
        attributes the trade to any strategy that recently signaled this symbol.
        """
        if strategy_name in self.strategy_stats:
            self.strategy_stats[strategy_name]['trades'] += 1
        
        # Attribute trade to strategies that signaled this symbol
        if symbol and symbol in self._active_signals:
            now = time.time()
            attributed = []
            expired = []
            for strat, ts in self._active_signals[symbol].items():
                if now - ts >= self._signal_ttl:
                    expired.append(strat)
                elif strat != strategy_name and strat in self.strategy_stats:
                    self.strategy_stats[strat]['trades'] += 1
                    attributed.append(strat)
            for strat in expired:
                del self._active_signals[symbol][strat]
            if attributed:
                logger.debug(f"📊 Trade {symbol} attributed to: {strategy_name} + {', '.join(attributed)}")

    async def scan_fast(self) -> List[Dict[str, Any]]:
        """
        Scan fast strategies (arbitrage).
        Called every scan loop (~0.15s).
        CROSS_EXCHANGE is handled by ArbitrageEngine.scan_once() — stats
        are fed back via record_engine_opportunities().
        TRIANGULAR, SMART_ORDER, VOLATILITY are scanned here.
        """
        opportunities = []

        try:
            # Increment call counters up front so dashboard always shows scan activity
            # (strategies are called every cycle, they just find 0 opportunities when data is pending)
            self.strategy_stats['CROSS_EXCHANGE']['calls'] += 1
            self.strategy_stats['TRIANGULAR']['calls'] += 1
            self.strategy_stats['SMART_ORDER']['calls'] += 1
            self.strategy_stats['VOLATILITY']['calls'] += 1

            # Update price history on every fast scan for slow strategies
            self._update_price_history()

            store = self._get_price_store()
            if not store:
                return opportunities
            snap = store.snapshot()

            # --- TRIANGULAR: Cross-exchange pairs arbitrage ---
            # Check if pair_a is mispriced on ex1 vs ex2, and pair_b is 
            # mispriced in the OPPOSITE direction. This creates a hedged 
            # arbitrage: go long pair_a cross-exchange + short pair_b cross-exchange.
            #
            # Real ROI = spread_a + spread_b - 4 * fee  (4 legs total)
            # where spread_a = bid_a_ex2/ask_a_ex1 - 1  (buy ex1, sell ex2)
            #       spread_b = bid_b_ex1/ask_b_ex2 - 1  (buy ex2, sell ex1)
            from core.exchange_config import EXCHANGE_PARAMS
            tri_pairs = [
                ('BTC-USDT', 'ETH-USDT'),
                ('BTC-USDT', 'SOL-USDT'),
                ('BTC-USDT', 'BNB-USDT'),
                ('ETH-USDT', 'SOL-USDT'),
                ('BTC-USDT', 'XRP-USDT'),
                ('ETH-USDT', 'BNB-USDT'),
                ('BTC-USDT', 'DOGE-USDT'),
                ('SOL-USDT', 'XRP-USDT'),
            ]
            best_tri_roi = -999
            best_tri_info = ""
            for pair_a, pair_b in tri_pairs:
                exmap_a = snap.get(pair_a, {})
                exmap_b = snap.get(pair_b, {})
                common_exs = [ex for ex in exmap_a if ex in exmap_b]
                if len(common_exs) < 2:
                    continue
                for i, ex1 in enumerate(common_exs):
                    rec_a1, rec_b1 = exmap_a[ex1], exmap_b[ex1]
                    bid_a1, ask_a1 = rec_a1.get("bid"), rec_a1.get("ask")
                    bid_b1, ask_b1 = rec_b1.get("bid"), rec_b1.get("ask")
                    if not (bid_a1 and ask_a1 and bid_b1 and ask_b1):
                        continue
                    if ask_a1 <= 0 or ask_b1 <= 0:
                        continue
                    for ex2 in common_exs[i+1:]:
                        rec_a2, rec_b2 = exmap_a[ex2], exmap_b[ex2]
                        bid_a2, ask_a2 = rec_a2.get("bid"), rec_a2.get("ask")
                        bid_b2, ask_b2 = rec_b2.get("bid"), rec_b2.get("ask")
                        if not (bid_a2 and ask_a2 and bid_b2 and ask_b2):
                            continue
                        if ask_a2 <= 0 or ask_b2 <= 0:
                            continue
                        fee1 = EXCHANGE_PARAMS.get(ex1, {}).get("taker", 0.001)
                        fee2 = EXCHANGE_PARAMS.get(ex2, {}).get("taker", 0.001)
                        
                        # Direction 1: buy pair_a on ex1, sell on ex2 + buy pair_b on ex2, sell on ex1
                        spread_a_fwd = (bid_a2 / ask_a1 - 1) * 100  # pair_a: ex1→ex2
                        spread_b_rev = (bid_b1 / ask_b2 - 1) * 100  # pair_b: ex2→ex1
                        fees_pct = (fee1 + fee2) * 2 * 100  # 4 legs total
                        roi1 = spread_a_fwd + spread_b_rev - fees_pct
                        
                        # Direction 2: buy pair_a on ex2, sell on ex1 + buy pair_b on ex1, sell on ex2
                        spread_a_rev = (bid_a1 / ask_a2 - 1) * 100
                        spread_b_fwd = (bid_b2 / ask_b1 - 1) * 100
                        roi2 = spread_a_rev + spread_b_fwd - fees_pct
                        
                        best_roi = max(roi1, roi2)
                        if best_roi > best_tri_roi:
                            best_tri_roi = best_roi
                            if roi1 >= roi2:
                                best_tri_info = f"{pair_a}:{ex1}→{ex2} + {pair_b}:{ex2}→{ex1}"
                            else:
                                best_tri_info = f"{pair_a}:{ex2}→{ex1} + {pair_b}:{ex1}→{ex2}"
                        
                        if best_roi > settings.MIN_NET_ROI_PCT:
                            if roi1 >= roi2:
                                direction = f"{pair_a}:{ex1}→{ex2} + {pair_b}:{ex2}→{ex1}"
                            else:
                                direction = f"{pair_a}:{ex2}→{ex1} + {pair_b}:{ex1}→{ex2}"
                            opportunities.append({
                                'strategy': 'TRIANGULAR',
                                'type': 'cross_exchange_triangle',
                                'route': direction,
                                'data': {'roi_pct': best_roi}
                            })
                            self.strategy_stats['TRIANGULAR']['opportunities'] += 1
                            self.strategy_stats['TRIANGULAR']['signals'] += 1
                            # Record signal for both pairs (trade attribution)
                            self.record_signal('TRIANGULAR', pair_a)
                            self.record_signal('TRIANGULAR', pair_b)
                            logger.info(f"   🔺 TRI: {direction} net_roi={best_roi:.3f}%")
            
            # Triangular near-misses tracked via best_tri_roi but not counted as signals
            # (only actual profitable routes increment signal counter)

            # --- SMART_ORDER: detect when spread is wide enough for limit orders ---
            # These are market condition SIGNALS (wide spread on single exchange).
            # Count as signals, not opportunities — actual opportunities are only
            # counted when _build_trade_from_signal() finds a profitable cross-exchange pair.
            from core.exchange_config import EXCHANGE_PARAMS as EP
            smart_order_signals_this_scan = 0
            for symbol, exmap in snap.items():
                for ex, rec in exmap.items():
                    bid, ask = rec.get("bid"), rec.get("ask")
                    if bid and ask and ask > 0:
                        spread_pct = (ask - bid) / ask * 100
                        # Use exchange-specific taker fee
                        fee_pct = EP.get(ex, {}).get("taker", 0.001) * 100
                        # Spread wide enough to profit from limit orders
                        if spread_pct > fee_pct * 2:
                            opportunities.append({
                                'strategy': 'SMART_ORDER',
                                'type': 'limit_opportunity',
                                'symbol': symbol,
                                'exchange': ex,
                                'data': {'spread_pct': spread_pct, 'ratio': spread_pct / fee_pct if fee_pct > 0 else spread_pct / 0.01}
                            })
                            self.record_signal('SMART_ORDER', symbol)
                            smart_order_signals_this_scan += 1
                            break  # one per symbol
            if smart_order_signals_this_scan > 0:
                self.strategy_stats['SMART_ORDER']['signals'] += 1  # 1 per scan, not per symbol
                self.strategy_stats['SMART_ORDER']['opportunities'] += 1

            # --- VOLATILITY: detect high short-term volatility ---
            # Only signal when volatility exceeds round-trip fees (otherwise noise)
            # Avg round-trip = MEXC(0.05%)+KuCoin(0.10%) = 0.15% minimum
            avg_round_trip_fee = 0.15  # cheapest cross-exchange path in %
            volatility_signals_this_scan = 0
            for symbol in list(self._price_history.keys()):
                prices = self._get_prices_list(symbol)
                if len(prices) < 10:
                    continue
                recent = prices[-10:]
                mean_p = sum(recent) / len(recent)
                if mean_p <= 0:
                    continue
                variance = sum((p - mean_p) ** 2 for p in recent) / len(recent)
                volatility = (variance ** 0.5) / mean_p * 100
                if volatility > avg_round_trip_fee:  # must exceed fees to be exploitable
                    opportunities.append({
                        'strategy': 'VOLATILITY',
                        'type': 'high_volatility',
                        'symbol': symbol,
                        'data': {'volatility_pct': volatility}
                    })
                    self.record_signal('VOLATILITY', symbol)
                    volatility_signals_this_scan += 1
            if volatility_signals_this_scan > 0:
                self.strategy_stats['VOLATILITY']['signals'] += 1  # 1 per scan, not per symbol
                self.strategy_stats['VOLATILITY']['opportunities'] += 1

        except Exception as e:
            logger.error(f"Error in fast strategy scan: {e}")

        return opportunities
    
    async def scan_slow(self) -> List[Dict[str, Any]]:
        """
        Scan slow strategies (position-based).
        Called every 5 minutes. Uses PriceStore data for analysis.
        """
        opportunities = []
        
        logger.info("⏰ Scanning 10 slow strategies...")
        
        try:
            scanners = [
                ('GRID_TRADING', self._scan_grid_trading),
                ('DCA', self._scan_dca),
                ('MARKET_MAKING', self._scan_market_making),
                ('PAIRS_TRADING', self._scan_pairs_trading),
                ('FUNDING_RATE', self._scan_funding_rate),
                ('VOLATILITY_ARB', self._scan_volatility_arb),
                ('INDEX_ARB', self._scan_index_arb),
                ('SPREAD_BETTING', self._scan_spread_betting),
                ('MOMENTUM', self._scan_momentum),
                ('BREAKOUT', self._scan_breakout),
            ]
            
            for name, scanner in scanners:
                try:
                    opps = await scanner()
                    if opps:
                        # Count signals for slow strategies (each opp = 1 signal)
                        self.strategy_stats[name]['signals'] += len(opps)
                        # Record active signals for trade attribution
                        for opp in opps:
                            sym = opp.get('symbol', '')
                            if sym:
                                self.record_signal(name, sym)
                    opportunities.extend(opps)
                except Exception as e:
                    logger.debug(f"{name} scan error: {e}")
            
            logger.info(f"   ✅ Slow scan complete: {len(opportunities)} opportunities found")
            
        except Exception as e:
            logger.error(f"Error in slow strategy scan: {e}")
        
        self.last_slow_scan = time.time()
        return opportunities
    
    def should_scan_slow(self) -> bool:
        """Check if it's time for slow strategy scan."""
        return (time.time() - self.last_slow_scan) >= self.slow_scan_interval
    
    # --- Individual strategy scanners using PriceStore data ---
    
    async def _scan_grid_trading(self) -> List[Dict[str, Any]]:
        """Grid Trading: check if current price deviates from SMA across all symbols.
        
        Only signals when deviation exceeds cheapest round-trip fees (0.15%),
        otherwise the grid rebalance would lose money on fees.
        """
        self.strategy_stats['GRID_TRADING']['calls'] += 1
        opportunities = []
        
        grid = getattr(self.bot_manager, 'grid_trading', None)
        if not grid:
            return opportunities
        
        # Minimum deviation must exceed cheapest round-trip fees
        min_deviation = 0.003  # 0.3% — covers fees (0.15%) + min profit (0.15%)
        symbols = getattr(settings, 'TRADING_SYMBOLS', ['BTC-USDT'])
        
        for symbol in symbols:
            mid = self._get_mid_price(symbol)
            if not mid:
                continue
            
            prices = self._get_prices_list(symbol)
            if len(prices) < 5:
                continue
            
            avg = sum(prices) / len(prices)
            deviation = abs(mid - avg) / avg if avg > 0 else 0
            
            if deviation > min_deviation:
                opportunities.append({
                    'strategy': 'GRID_TRADING',
                    'type': 'rebalance',
                    'symbol': symbol,
                    'data': {'mid_price': mid, 'avg_price': avg, 'deviation_pct': deviation * 100}
                })
                self.strategy_stats['GRID_TRADING']['opportunities'] += 1
                logger.info(f"   📊 GRID: {symbol} deviation {deviation*100:.2f}% from center")
        
        return opportunities
    
    async def _scan_dca(self) -> List[Dict[str, Any]]:
        """DCA: check if current price is below SMA across all symbols.
        
        Only triggers on significant dips (>1% below SMA) because the 
        cross-exchange execution costs ~0.15% minimum in fees.
        Deeper dips get higher confidence → lower ROI threshold.
        """
        self.strategy_stats['DCA']['calls'] += 1
        opportunities = []
        
        dca = getattr(self.bot_manager, 'dca_strategy', None)
        if not dca:
            return opportunities
        
        symbols = getattr(settings, 'TRADING_SYMBOLS', ['BTC-USDT'])
        
        for symbol in symbols:
            prices = self._get_prices_list(symbol)
            if len(prices) < 20:
                continue
            
            current = prices[-1]
            sma20 = sum(prices[-20:]) / 20
            
            if current < sma20 * 0.99:  # 1% below SMA (covers fees + gives statistical edge)
                dip_pct = ((sma20 - current) / sma20) * 100
                opportunities.append({
                    'strategy': 'DCA',
                    'type': 'accumulation',
                    'symbol': symbol,
                    'data': {'price': current, 'sma20': sma20, 'dip_pct': dip_pct}
                })
                self.strategy_stats['DCA']['opportunities'] += 1
                logger.info(f"   📊 DCA: {symbol} is {dip_pct:.2f}% below SMA20")
        
        return opportunities
    
    async def _scan_market_making(self) -> List[Dict[str, Any]]:
        """Market Making: check if cross-exchange spread covers fees + min ROI."""
        self.strategy_stats['MARKET_MAKING']['calls'] += 1
        opportunities = []
        
        mm = getattr(self.bot_manager, 'market_making', None)
        if not mm:
            return opportunities
        
        store = self._get_price_store()
        if not store:
            return opportunities
        snap = store.snapshot()
        from core.exchange_config import EXCHANGE_PARAMS
        
        # Check cross-exchange spread for each symbol
        for symbol, exmap in snap.items():
            if len(exmap) < 2:
                continue
            best_bid, best_ask = 0.0, float('inf')
            bid_ex, ask_ex = '', ''
            for ex, rec in exmap.items():
                b, a = rec.get("bid", 0), rec.get("ask", 0)
                if b and b > best_bid:
                    best_bid, bid_ex = b, ex
                if a and a < best_ask:
                    best_ask, ask_ex = a, ex
            if best_bid > best_ask and bid_ex != ask_ex:
                spread_pct = (best_bid - best_ask) / best_ask
                # Fee-aware threshold: spread must cover both sides' taker fees
                buy_fee = EXCHANGE_PARAMS.get(ask_ex, {}).get("taker", 0.001)
                sell_fee = EXCHANGE_PARAMS.get(bid_ex, {}).get("taker", 0.001)
                min_spread = buy_fee + sell_fee  # e.g. 0.001+0.001 = 0.002 (0.20%)
                if spread_pct > min_spread:  # Spread must exceed total fees
                    opportunities.append({
                        'strategy': 'MARKET_MAKING',
                        'type': 'cross_spread',
                        'symbol': symbol,
                        'data': {'spread_pct': spread_pct * 100, 'bid_ex': bid_ex, 'ask_ex': ask_ex}
                    })
                    self.strategy_stats['MARKET_MAKING']['opportunities'] += 1
                    logger.info(f"   📊 MM: {symbol} cross-spread {spread_pct*100:.3f}% ({ask_ex}→{bid_ex})")
                    break  # One signal per scan
        
        return opportunities
    
    async def _scan_pairs_trading(self) -> List[Dict[str, Any]]:
        """Pairs Trading: z-score on price ratio between correlated assets.
        
        Uses z-score threshold of 2.0 (stronger than default 1.5) for small capital
        to reduce false signals. Confidence from z>2.0 provides up to 80% fee reduction.
        """
        self.strategy_stats['PAIRS_TRADING']['calls'] += 1
        opportunities = []
        
        pairs = getattr(self.bot_manager, 'pairs_trading', None)
        if not pairs:
            return opportunities
        
        pair1 = getattr(pairs, 'pair1', 'BTC-USDT')
        pair2 = getattr(pairs, 'pair2', 'ETH-USDT')
        
        prices1 = self._get_prices_list(pair1)
        prices2 = self._get_prices_list(pair2)
        
        min_len = min(len(prices1), len(prices2))
        if min_len < 20:
            return opportunities
        
        # Calculate ratio and z-score (skip zero prices)
        ratios = [p1 / p2 for p1, p2 in zip(prices1[-min_len:], prices2[-min_len:]) if p2 > 0]
        if len(ratios) < 20:
            return opportunities
        
        # Feed ratio into strategy's internal state if possible
        entry_z = getattr(pairs, 'entry_z', 2.0)  # 2.0 default (was 1.5) — stronger signal for small capital
        
        mean_ratio = sum(ratios) / len(ratios)
        std_ratio = (sum((r - mean_ratio) ** 2 for r in ratios) / len(ratios)) ** 0.5
        
        if std_ratio > 0:
            z_score = (ratios[-1] - mean_ratio) / std_ratio
        else:
            z_score = 0
        
        if abs(z_score) > entry_z:
            direction = 'short_pair1_long_pair2' if z_score > 0 else 'long_pair1_short_pair2'
            opportunities.append({
                'strategy': 'PAIRS_TRADING',
                'type': 'correlation',
                'symbol': f"{pair1}/{pair2}",
                'data': {'z_score': z_score, 'direction': direction, 'ratio': ratios[-1]}
            })
            self.strategy_stats['PAIRS_TRADING']['opportunities'] += 1
            logger.info(f"   📊 PAIRS: {pair1}/{pair2} z={z_score:.2f} → {direction}")
        
        return opportunities
    
    async def _scan_funding_rate(self) -> List[Dict[str, Any]]:
        """Funding Rate: detect premium/discount between exchange prices.
        
        Only signals when deviation exceeds trading fees, so the opportunity
        is actually profitable to capture.
        """
        self.strategy_stats['FUNDING_RATE']['calls'] += 1
        opportunities = []
        
        store = self._get_price_store()
        if not store:
            return opportunities
        
        snap = store.snapshot()
        from core.exchange_config import EXCHANGE_PARAMS
        
        # Check for price deviations between exchanges (proxy for funding rate)
        for symbol, exmap in snap.items():
            if len(exmap) < 2:
                continue
            
            prices = {}
            for ex, rec in exmap.items():
                bid = rec.get("bid")
                ask = rec.get("ask")
                if bid and ask:
                    prices[ex] = (bid + ask) / 2
            
            if len(prices) < 2:
                continue
            
            vals = list(prices.values())
            avg_price = sum(vals) / len(vals)
            
            for ex, price in prices.items():
                deviation = ((price - avg_price) / avg_price) * 100
                # Fee-aware: deviation must exceed fees to be profitable
                # Max fees = buy on cheapest (0.10%) + sell on this (0.20%) = 0.30%
                ex_fee = EXCHANGE_PARAMS.get(ex, {}).get("taker", 0.001) * 100
                avg_fee = sum(EXCHANGE_PARAMS.get(e, {}).get("taker", 0.001) for e in prices) / len(prices) * 100
                min_deviation = ex_fee + avg_fee  # e.g. 0.10% + 0.12% = 0.22%
                if abs(deviation) > min_deviation:  # Must exceed total fees
                    opportunities.append({
                        'strategy': 'FUNDING_RATE',
                        'type': 'premium',
                        'symbol': symbol,
                        'data': {'exchange': ex, 'deviation_pct': deviation, 'price': price}
                    })
                    self.strategy_stats['FUNDING_RATE']['opportunities'] += 1
                    logger.info(f"   📊 FUNDING: {symbol} {ex} {deviation:+.3f}% vs average")
                    break  # One signal per symbol
        
        return opportunities
    
    async def _scan_volatility_arb(self) -> List[Dict[str, Any]]:
        """Volatility Arb: detect spread width differences between exchanges.
        
        When one exchange has a much wider spread, the narrow-spread exchange
        has tighter pricing — we can buy there and sell on the wide-spread one
        (or vice versa). Only signals when the spread DIFFERENCE covers fees.
        """
        self.strategy_stats['VOLATILITY_ARB']['calls'] += 1
        opportunities = []
        
        store = self._get_price_store()
        if not store:
            return opportunities
        
        snap = store.snapshot()
        from core.exchange_config import EXCHANGE_PARAMS
        
        for symbol, exmap in snap.items():
            if len(exmap) < 2:
                continue
            
            spreads = {}
            for ex, rec in exmap.items():
                bid = rec.get("bid")
                ask = rec.get("ask")
                if bid and ask and ask > 0:
                    spreads[ex] = (ask - bid) / ask
            
            if len(spreads) < 2:
                continue
            
            vals = list(spreads.values())
            max_spread = max(vals)
            min_spread = min(vals)
            
            # Signal when spread difference is large enough to cover fees
            wide_ex = max(spreads, key=spreads.get)
            narrow_ex = min(spreads, key=spreads.get)
            spread_diff = max_spread - min_spread
            # Fee threshold for trading between these two exchanges
            fee_wide = EXCHANGE_PARAMS.get(wide_ex, {}).get("taker", 0.001)
            fee_narrow = EXCHANGE_PARAMS.get(narrow_ex, {}).get("taker", 0.001)
            fee_threshold = fee_wide + fee_narrow  # e.g. 0.002 = 0.20%
            
            if spread_diff > fee_threshold and max_spread > min_spread * 2:
                opportunities.append({
                    'strategy': 'VOLATILITY_ARB',
                    'type': 'spread_diff',
                    'symbol': symbol,
                    'data': {
                        'wide_exchange': wide_ex, 'wide_spread': max_spread * 100,
                        'narrow_exchange': narrow_ex, 'narrow_spread': min_spread * 100
                    }
                })
                self.strategy_stats['VOLATILITY_ARB']['opportunities'] += 1
                logger.info(f"   📊 VOLARB: {symbol} spread diff {wide_ex}={max_spread*100:.3f}% vs {narrow_ex}={min_spread*100:.3f}%")
                break  # One per scan
        
        return opportunities
    
    async def _scan_index_arb(self) -> List[Dict[str, Any]]:
        """Index Arb: compare each symbol's exchange price to its composite average.
        
        Only signals when deviation exceeds trading fees.
        """
        self.strategy_stats['INDEX_ARB']['calls'] += 1
        opportunities = []
        
        store = self._get_price_store()
        if not store:
            return opportunities
        
        snap = store.snapshot()
        from core.exchange_config import EXCHANGE_PARAMS
        
        for symbol, exmap in snap.items():
            prices = {}
            for ex, rec in exmap.items():
                bid = rec.get("bid")
                ask = rec.get("ask")
                if bid and ask:
                    prices[ex] = (bid + ask) / 2
            
            if len(prices) < 2:
                continue
            
            avg = sum(prices.values()) / len(prices)
            
            for ex, price in prices.items():
                dev = ((price - avg) / avg) * 100
                # Fee-aware: deviation must exceed fees to trade profitably
                ex_fee = EXCHANGE_PARAMS.get(ex, {}).get("taker", 0.001) * 100
                avg_fee = sum(EXCHANGE_PARAMS.get(e, {}).get("taker", 0.001) for e in prices) / len(prices) * 100
                min_dev = ex_fee + avg_fee  # e.g. 0.10% + 0.12% = 0.22%
                if abs(dev) > min_dev:  # Must exceed total fees
                    opportunities.append({
                        'strategy': 'INDEX_ARB',
                        'type': 'index_deviation',
                        'symbol': symbol,
                        'data': {'exchange': ex, 'deviation_pct': dev, 'price': price, 'index_price': avg}
                    })
                    self.strategy_stats['INDEX_ARB']['opportunities'] += 1
                    logger.info(f"   📊 INDEX: {symbol} {ex} {dev:+.3f}% vs composite")
                    break  # One signal per symbol
        
        return opportunities
    
    async def _scan_spread_betting(self) -> List[Dict[str, Any]]:
        """Spread Betting: z-score on cross-exchange spread history.
        
        Uses z-score threshold of 2.0 (stronger than default 1.5) to avoid
        false signals on small capital. Mean-reversion signals provide confidence
        for fee-reduced execution.
        """
        self.strategy_stats['SPREAD_BETTING']['calls'] += 1
        opportunities = []
        
        spread_strat = getattr(self.bot_manager, 'spread_betting', None)
        if not spread_strat:
            return opportunities
        
        pair1 = getattr(spread_strat, 'pair1', 'BTC-USDT')
        pair2 = getattr(spread_strat, 'pair2', 'ETH-USDT')
        
        prices1 = self._get_prices_list(pair1)
        prices2 = self._get_prices_list(pair2)
        
        min_len = min(len(prices1), len(prices2))
        if min_len < 20:
            return opportunities
        
        # Calculate spread (difference ratio, skip zero prices)
        spreads = [(p1 - p2) / p1 for p1, p2 in zip(prices1[-min_len:], prices2[-min_len:]) if p1 > 0]
        if len(spreads) < 20:
            return opportunities
        
        mean_s = sum(spreads) / len(spreads)
        std_s = (sum((s - mean_s) ** 2 for s in spreads) / len(spreads)) ** 0.5
        
        if std_s > 0:
            z = (spreads[-1] - mean_s) / std_s
        else:
            z = 0
        
        entry_z = getattr(spread_strat, 'entry_z_score', 2.0)  # 2.0 default (was 1.5)
        if abs(z) > entry_z:
            opportunities.append({
                'strategy': 'SPREAD_BETTING',
                'type': 'mean_reversion',
                'symbol': f"{pair1}/{pair2}",
                'data': {'z_score': z, 'spread': spreads[-1]}
            })
            self.strategy_stats['SPREAD_BETTING']['opportunities'] += 1
            logger.info(f"   📊 SPREAD: {pair1}/{pair2} z={z:.2f}")
        
        return opportunities
    
    async def _scan_momentum(self) -> List[Dict[str, Any]]:
        """Momentum: RSI-based trend detection.
        
        Only signals on extreme RSI (<30 or >70) to ensure statistical edge
        exceeds trading fees. The RSI extremity maps to confidence (0.4-1.0)
        which reduces the min_roi threshold for cross-exchange execution.
        """
        self.strategy_stats['MOMENTUM']['calls'] += 1
        opportunities = []
        
        momentum = getattr(self.bot_manager, 'momentum_strategy', None)
        if not momentum:
            return opportunities
        
        symbols = getattr(settings, 'TRADING_SYMBOLS', ['BTC-USDT'])
        
        for symbol in symbols:
            prices = self._get_prices_list(symbol)
            if len(prices) < 15:
                continue
            
            try:
                if hasattr(momentum, 'analyze'):
                    signal = momentum.analyze(symbol, prices)
                    if signal and getattr(signal, 'strength', 0) >= 0.3:  # min strength filter
                        opportunities.append({
                            'strategy': 'MOMENTUM',
                            'type': 'trend',
                            'symbol': symbol,
                            'data': {
                                'signal_type': signal.signal_type,
                                'rsi': signal.rsi,
                                'strength': signal.strength
                            }
                        })
                        self.strategy_stats['MOMENTUM']['opportunities'] += 1
                        logger.info(f"   📊 MOMENTUM: {symbol} {signal.signal_type} RSI={signal.rsi:.1f}")
            except Exception as e:
                logger.debug(f"Momentum analyze error for {symbol}: {e}")
        
        return opportunities
    
    async def _scan_breakout(self) -> List[Dict[str, Any]]:
        """Breakout: technical breakout detection via support/resistance levels.
        
        Only signals when the breakout move is significant (volume_proxy > 0.002 = 0.2%)
        to filter out noise. Small capital ($14) can't afford false breakout whipsaws.
        """
        self.strategy_stats['BREAKOUT']['calls'] += 1
        opportunities = []
        
        breakout = getattr(self.bot_manager, 'breakout_strategy', None)
        if not breakout:
            return opportunities
        
        min_move_pct = 0.002  # 0.2% minimum price move to consider a breakout
        symbols = getattr(settings, 'TRADING_SYMBOLS', ['BTC-USDT'])
        
        for symbol in symbols:
            prices = self._get_prices_list(symbol)
            if len(prices) < 15:
                continue
            
            current_price = prices[-1]
            prev_price = prices[-2] if len(prices) >= 2 else 0
            volume_proxy = abs(current_price - prev_price) / prev_price if prev_price > 0 else 0
            
            if volume_proxy < min_move_pct:  # skip tiny moves
                continue
            
            try:
                if hasattr(breakout, 'analyze'):
                    signal = breakout.analyze(symbol, current_price, volume_proxy)
                    if signal:
                        opportunities.append({
                            'strategy': 'BREAKOUT',
                            'type': 'technical',
                            'symbol': symbol,
                            'data': signal
                        })
                        self.strategy_stats['BREAKOUT']['opportunities'] += 1
                        logger.info(f"   📊 BREAKOUT: {symbol} {signal.get('type', 'unknown')} @ {current_price:.2f}")
            except Exception as e:
                logger.debug(f"Breakout analyze error for {symbol}: {e}")
        
        return opportunities
    
    def print_stats(self):
        """Print strategy statistics."""
        logger.info("=" * 60)
        logger.info("STRATEGY DISPATCHER STATISTICS")
        logger.info("=" * 60)
        
        total_calls = sum(s['calls'] for s in self.strategy_stats.values())
        total_opps = sum(s['opportunities'] for s in self.strategy_stats.values())
        
        logger.info(f"Total Strategy Calls: {total_calls}")
        logger.info(f"Total Opportunities: {total_opps}")
        logger.info("")
        
        for strategy, stats in self.strategy_stats.items():
            if stats['calls'] > 0:
                hit_rate = (stats['opportunities'] / stats['calls'] * 100) if stats['calls'] > 0 else 0
                logger.info(f"{strategy:20} | Calls: {stats['calls']:6} | Opps: {stats['opportunities']:6} | Rate: {hit_rate:5.2f}%")
        
        logger.info("=" * 60)
