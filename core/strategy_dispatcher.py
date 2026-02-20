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
        self.slow_scan_interval = 300  # 5 minutes
        
        # Price history for strategies that need time series
        # symbol -> deque of (timestamp, mid_price)
        self._price_history: Dict[str, deque] = {}
        self._max_history = 200  # Keep 200 data points per symbol
        
        # Strategy performance tracking
        self.strategy_stats = {
            'CROSS_EXCHANGE': {'calls': 0, 'opportunities': 0},
            'TRIANGULAR': {'calls': 0, 'opportunities': 0},
            'SMART_ORDER': {'calls': 0, 'opportunities': 0},
            'VOLATILITY': {'calls': 0, 'opportunities': 0},
            'GRID_TRADING': {'calls': 0, 'opportunities': 0},
            'DCA': {'calls': 0, 'opportunities': 0},
            'MARKET_MAKING': {'calls': 0, 'opportunities': 0},
            'PAIRS_TRADING': {'calls': 0, 'opportunities': 0},
            'FUNDING_RATE': {'calls': 0, 'opportunities': 0},
            'VOLATILITY_ARB': {'calls': 0, 'opportunities': 0},
            'INDEX_ARB': {'calls': 0, 'opportunities': 0},
            'SPREAD_BETTING': {'calls': 0, 'opportunities': 0},
            'MOMENTUM': {'calls': 0, 'opportunities': 0},
            'BREAKOUT': {'calls': 0, 'opportunities': 0},
        }
        
        fast_names = ['CROSS_EXCHANGE', 'TRIANGULAR', 'SMART_ORDER', 'VOLATILITY']
        slow_names = [k for k in self.strategy_stats if k not in fast_names]
        logger.info(f"✅ StrategyDispatcher initialized with {len(self.strategy_stats)} strategies")
        logger.info(f"   Fast strategies ({len(fast_names)}): {', '.join(fast_names)}")
        logger.info(f"   Slow strategies ({len(slow_names)}): {', '.join(slow_names)}")
    
    def _get_price_store(self):
        """Get the PriceStore from bot_manager."""
        return getattr(self.bot_manager, 'price_store', None)
    
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
    
    async def scan_fast(self) -> List[Dict[str, Any]]:
        """
        Scan fast strategies (arbitrage).
        Called every scan loop (~0.15s).
        """
        opportunities = []
        
        try:
            # Fast strategies are handled by ArbitrageEngine.scan_once()
            # We track call counts here for statistics
            self.strategy_stats['CROSS_EXCHANGE']['calls'] += 1
            self.strategy_stats['TRIANGULAR']['calls'] += 1
            self.strategy_stats['SMART_ORDER']['calls'] += 1
            self.strategy_stats['VOLATILITY']['calls'] += 1
            
            # Update price history on every fast scan for slow strategies to use
            self._update_price_history()
            
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
        """Grid Trading: check if current price is near grid levels."""
        self.strategy_stats['GRID_TRADING']['calls'] += 1
        opportunities = []
        
        grid = getattr(self.bot_manager, 'grid_trading', None)
        if not grid:
            return opportunities
        
        symbol = getattr(grid, 'symbol', 'BTC-USDT')
        mid = self._get_mid_price(symbol)
        if not mid:
            return opportunities
        
        # Analyze grid position: is price near the edges of the range?
        range_pct = getattr(grid, 'price_range_pct', 0.1)
        prices = self._get_prices_list(symbol)
        if len(prices) < 5:
            return opportunities
        
        avg = sum(prices) / len(prices)
        deviation = abs(mid - avg) / avg if avg > 0 else 0
        
        # Signal when price is moving away from center (grid needs rebalancing)
        if deviation > range_pct * 0.3:
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
        """DCA: check if current price is below SMA (buy-the-dip signal)."""
        self.strategy_stats['DCA']['calls'] += 1
        opportunities = []
        
        dca = getattr(self.bot_manager, 'dca_strategy', None)
        if not dca:
            return opportunities
        
        symbol = getattr(dca, 'symbol', 'BTC-USDT')
        prices = self._get_prices_list(symbol)
        if len(prices) < 20:
            return opportunities
        
        current = prices[-1]
        sma20 = sum(prices[-20:]) / 20
        
        # DCA signal: price is below 20-period SMA (dip buying)
        if current < sma20 * 0.99:  # 1% below SMA
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
        """Market Making: check if spread is wide enough for profitability."""
        self.strategy_stats['MARKET_MAKING']['calls'] += 1
        opportunities = []
        
        mm = getattr(self.bot_manager, 'market_making', None)
        if not mm:
            return opportunities
        
        symbol = getattr(mm, 'symbol', 'BTC-USDT')
        spread = self._get_spread(symbol)
        if spread is None:
            return opportunities
        
        # Market making is profitable when spread > 2x taker fee
        min_spread = getattr(mm, 'spread_pct', 0.002)
        if spread > min_spread:
            opportunities.append({
                'strategy': 'MARKET_MAKING',
                'type': 'liquidity',
                'symbol': symbol,
                'data': {'spread_pct': spread * 100, 'min_spread_pct': min_spread * 100}
            })
            self.strategy_stats['MARKET_MAKING']['opportunities'] += 1
            logger.info(f"   📊 MM: {symbol} spread {spread*100:.3f}% > min {min_spread*100:.3f}%")
        
        return opportunities
    
    async def _scan_pairs_trading(self) -> List[Dict[str, Any]]:
        """Pairs Trading: check z-score of price ratio between two assets."""
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
        entry_z = getattr(pairs, 'entry_z', 2.0)
        
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
        """Funding Rate: detect premium/discount between exchange prices."""
        self.strategy_stats['FUNDING_RATE']['calls'] += 1
        opportunities = []
        
        store = self._get_price_store()
        if not store:
            return opportunities
        
        snap = store.snapshot()
        
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
                if abs(deviation) > 0.3:  # >0.3% premium/discount
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
        """Volatility Arb: detect spread width differences between exchanges."""
        self.strategy_stats['VOLATILITY_ARB']['calls'] += 1
        opportunities = []
        
        store = self._get_price_store()
        if not store:
            return opportunities
        
        snap = store.snapshot()
        
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
            
            # Signal when one exchange has significantly wider spread
            if max_spread > 0 and min_spread > 0 and max_spread > min_spread * 2:
                wide_ex = max(spreads, key=spreads.get)
                narrow_ex = min(spreads, key=spreads.get)
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
        """Index Arb: compare BTC price to average of all tracked prices."""
        self.strategy_stats['INDEX_ARB']['calls'] += 1
        opportunities = []
        
        # Use BTC as index proxy, compare to avg mid across exchanges
        mid = self._get_mid_price('BTC-USDT')
        if not mid:
            return opportunities
        
        store = self._get_price_store()
        if not store:
            return opportunities
        
        snap = store.snapshot()
        btc_prices = {}
        for ex, rec in snap.get('BTC-USDT', {}).items():
            bid = rec.get("bid")
            ask = rec.get("ask")
            if bid and ask:
                btc_prices[ex] = (bid + ask) / 2
        
        if len(btc_prices) < 2:
            return opportunities
        
        avg = sum(btc_prices.values()) / len(btc_prices)
        
        for ex, price in btc_prices.items():
            dev = ((price - avg) / avg) * 100
            if abs(dev) > 0.1:  # > 0.1% deviation from composite
                opportunities.append({
                    'strategy': 'INDEX_ARB',
                    'type': 'index_deviation',
                    'symbol': 'BTC-USDT',
                    'data': {'exchange': ex, 'deviation_pct': dev, 'price': price, 'index_price': avg}
                })
                self.strategy_stats['INDEX_ARB']['opportunities'] += 1
                logger.info(f"   📊 INDEX: BTC-USDT {ex} {dev:+.3f}% vs composite")
                break
        
        return opportunities
    
    async def _scan_spread_betting(self) -> List[Dict[str, Any]]:
        """Spread Betting: z-score on cross-exchange spread history."""
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
        if min_len < 30:
            return opportunities
        
        # Calculate spread (difference ratio, skip zero prices)
        spreads = [(p1 - p2) / p1 for p1, p2 in zip(prices1[-min_len:], prices2[-min_len:]) if p1 > 0]
        if len(spreads) < 30:
            return opportunities
        
        mean_s = sum(spreads) / len(spreads)
        std_s = (sum((s - mean_s) ** 2 for s in spreads) / len(spreads)) ** 0.5
        
        if std_s > 0:
            z = (spreads[-1] - mean_s) / std_s
        else:
            z = 0
        
        entry_z = getattr(spread_strat, 'entry_z_score', 2.0)
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
        """Momentum: call analyze() on MomentumStrategy with PriceStore data."""
        self.strategy_stats['MOMENTUM']['calls'] += 1
        opportunities = []
        
        momentum = getattr(self.bot_manager, 'momentum_strategy', None)
        if not momentum:
            return opportunities
        
        symbols = getattr(settings, 'TRADING_SYMBOLS', ['BTC-USDT'])
        
        for symbol in symbols:
            prices = self._get_prices_list(symbol)
            if len(prices) < 20:
                continue
            
            # MomentumStrategy.analyze(symbol, prices) returns a MomentumSignal or None
            if hasattr(momentum, 'analyze'):
                signal = momentum.analyze(symbol, prices)
                if signal:
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
        
        return opportunities
    
    async def _scan_breakout(self) -> List[Dict[str, Any]]:
        """Breakout: call analyze() on BreakoutStrategy with PriceStore data."""
        self.strategy_stats['BREAKOUT']['calls'] += 1
        opportunities = []
        
        breakout = getattr(self.bot_manager, 'breakout_strategy', None)
        if not breakout:
            return opportunities
        
        symbols = getattr(settings, 'TRADING_SYMBOLS', ['BTC-USDT'])
        
        for symbol in symbols:
            prices = self._get_prices_list(symbol)
            if len(prices) < 50:
                continue
            
            current_price = prices[-1]
            # Use price change as volume proxy (we don't have real volume data)
            prev_price = prices[-2] if len(prices) >= 2 else 0
            volume_proxy = abs(current_price - prev_price) / prev_price if prev_price > 0 else 0
            
            # BreakoutStrategy.analyze(symbol, price, volume) returns signal dict or None
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
