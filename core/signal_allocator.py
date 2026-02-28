#!/usr/bin/env python3
"""
Signal-Based Capital Allocator — distributes USDT across exchanges
toward the coins that have the most/best trading signals.

For cross-exchange arbitrage, you need BASE COIN inventory on the sell
exchange. This module tracks which symbols produce the most signals
and recommends pre-positioning capital into those base coins.

Example:
  - APT-USDT has had 15 profitable signals in the last hour (best performer)
  - LINK-USDT has 10 signals
  - Module recommends: allocate 30% of idle USDT to APT, 20% to LINK
  - On each exchange, convert some USDT → APT so the bot can sell APT immediately

This is HFT-style inventory management: maintain small positions in
"hot" coins across all exchanges so both sides of arbitrage can execute
without waiting for settlement.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

import settings

logger = logging.getLogger("signal_allocator")


@dataclass
class SignalRecord:
    """Single signal event for tracking."""
    symbol: str
    strategy: str
    exchange: str
    timestamp: float
    roi_pct: float = 0.0
    executed: bool = False


class SignalAllocator:
    """
    Tracks trading signal frequency and quality per symbol, then recommends
    optimal USDT allocation across exchanges for inventory pre-positioning.

    Architecture:
    1. record_signal() — called whenever any strategy finds an opportunity
    2. record_trade() — called when a trade actually executes
    3. get_allocation() — returns recommended % allocation per symbol
    4. get_inventory_orders() — returns specific buy orders to pre-position

    Signal scoring:
    - Recent signals weighted more (exponential decay, 1-hour half-life)
    - Executed signals (actual trades) weighted 5× more than raw signals
    - Higher ROI signals weighted proportionally
    """

    # Decay half-life in seconds (signals older than this count for less)
    DECAY_HALF_LIFE = 3600.0  # 1 hour

    # Maximum signal history to keep (prevents unbounded memory)
    MAX_HISTORY = 5000

    # Minimum signals before a symbol gets allocation
    MIN_SIGNALS_FOR_ALLOCATION = 3

    # Maximum fraction of idle capital to allocate to pre-positioning
    MAX_PREPOSITION_PCT = 0.50  # Use max 50% of USDT for inventory

    # Maximum allocation to any single symbol
    MAX_SINGLE_SYMBOL_PCT = 0.25  # Max 25% of USDT in one coin

    # Minimum order size for pre-positioning (lower than trade minimum)
    MIN_PREPOSITION_USDT = 1.0  # $1 minimum for inventory orders

    # Rebalance thresholds
    REBALANCE_THRESHOLD_PCT = 0.30  # Buy if holding < 30% of target
    MAX_SINGLE_BUY_PCT = 0.50  # Max 50% of available USDT per single buy
    LIQUIDATION_PCT = 0.80  # Sell 80% of non-allocated coins, keep 20% reserve

    # Weight multiplier for executed trades vs raw signals
    EXECUTED_WEIGHT = 5.0

    # Reactive rebalance: how many missed trades trigger immediate rebalance
    MISS_THRESHOLD = 2  # 2 misses in MISS_WINDOW → urgent rebalance
    MISS_WINDOW = 60.0  # seconds

    def __init__(self, balance_manager=None):
        self.balance_manager = balance_manager
        self._signals: List[SignalRecord] = []
        self._symbol_scores: Dict[str, float] = {}
        self._last_update = 0.0
        self._update_interval = 30.0  # Recalculate every 30s

        # Missed opportunity tracking for reactive rebalance
        self._misses: List[Dict] = []  # [{symbol, exchange, side, timestamp}]
        self._urgent_rebalance_needed = False
        self._urgent_symbols: Dict[str, float] = {}  # symbol → timestamp of last miss

        logger.info("✅ SignalAllocator initialized (HFT-style inventory management)")

    def record_signal(
        self,
        symbol: str,
        strategy: str,
        exchange: str = "",
        roi_pct: float = 0.0,
        executed: bool = False
    ):
        """Record a signal for allocation scoring.

        Args:
            symbol: Trading symbol (e.g. 'APT-USDT')
            strategy: Strategy that generated signal
            exchange: Exchange where signal was found
            roi_pct: Expected ROI percentage
            executed: Whether the signal led to an actual trade
        """
        self._signals.append(SignalRecord(
            symbol=symbol,
            strategy=strategy,
            exchange=exchange,
            timestamp=time.time(),
            roi_pct=roi_pct,
            executed=executed,
        ))

        # Trim history
        if len(self._signals) > self.MAX_HISTORY:
            self._signals = self._signals[-self.MAX_HISTORY:]

    def record_trade(self, symbol: str, strategy: str, exchange: str, roi_pct: float):
        """Convenience: record an executed trade signal (weighted 5× more)."""
        self.record_signal(symbol, strategy, exchange, roi_pct, executed=True)

    def record_miss(self, symbol: str, exchange: str, side: str = 'sell'):
        """Record a missed opportunity (trade blocked due to missing inventory).
        
        When 2+ misses occur for the same symbol within 60 seconds,
        triggers urgent rebalance to pre-position that coin.
        
        Args:
            symbol: Trading symbol (e.g. 'APT-USDT')
            exchange: Exchange that was missing inventory
            side: 'sell' (missing base coin) or 'buy' (missing USDT)
        """
        now = time.time()
        self._misses.append({
            'symbol': symbol,
            'exchange': exchange,
            'side': side,
            'timestamp': now,
        })
        
        # Trim old misses
        cutoff = now - self.MISS_WINDOW
        self._misses = [m for m in self._misses if m['timestamp'] > cutoff]
        
        # Count recent misses for this symbol
        recent_for_symbol = sum(
            1 for m in self._misses 
            if m['symbol'] == symbol and m['timestamp'] > cutoff
        )
        
        if recent_for_symbol >= self.MISS_THRESHOLD:
            self._urgent_rebalance_needed = True
            self._urgent_symbols[symbol] = now
            logger.info(
                f"🔥 URGENT: {symbol} missed {recent_for_symbol}× in {self.MISS_WINDOW:.0f}s "
                f"(no {side}-side inventory on {exchange}) → triggering immediate rebalance"
            )
            # Boost the signal score for this symbol (3× miss signals)
            for _ in range(3):
                self.record_signal(symbol, 'MISS_REACTIVE', exchange, roi_pct=0.5, executed=False)

    def needs_urgent_rebalance(self) -> bool:
        """Check if reactive rebalance is needed (missed opportunities detected)."""
        if self._urgent_rebalance_needed:
            self._urgent_rebalance_needed = False
            return True
        return False

    def get_max_preposition_coins(self) -> int:
        """Calculate how many different coins to pre-position based on capital.
        
        With small capital ($10/exchange): 1-2 coins
        With medium capital ($100/exchange): 3-5 coins
        With large capital ($1000+/exchange): 5-8 coins
        """
        if not self.balance_manager:
            return 3
        
        # Get average USDT per exchange
        total_usdt = 0
        num_exchanges = 0
        for exchange, balances in self.balance_manager.balances.items():
            usdt = balances.get('USDT', 0)
            total_usdt += usdt
            num_exchanges += 1
        
        if num_exchanges == 0:
            return 3
        
        avg_per_exchange = total_usdt / num_exchanges
        
        if avg_per_exchange < 20:
            return 1  # Very small: only 1 coin
        elif avg_per_exchange < 50:
            return 2  # Small: 2 coins
        elif avg_per_exchange < 200:
            return 4  # Medium: up to 4 coins
        elif avg_per_exchange < 1000:
            return 6  # Large: up to 6 coins
        else:
            return 8  # Very large: up to 8 coins

    def _compute_scores(self) -> Dict[str, float]:
        """Compute weighted signal scores per symbol.

        Uses exponential decay so recent signals matter more.
        Returns dict of symbol → score.
        """
        now = time.time()
        scores: Dict[str, float] = defaultdict(float)

        for sig in self._signals:
            age = now - sig.timestamp
            # Exponential decay: weight halves every DECAY_HALF_LIFE seconds
            decay = 0.5 ** (age / self.DECAY_HALF_LIFE) if age > 0 else 1.0

            # Base weight = 1.0 for signal, 5.0 for executed trade
            weight = self.EXECUTED_WEIGHT if sig.executed else 1.0

            # ROI bonus: higher ROI signals get proportionally more weight
            # 0.1% ROI → 2× weight, 1.0% ROI → 11× weight
            roi_bonus = 1.0 + max(sig.roi_pct, 0) * 10.0

            scores[sig.symbol] += weight * decay * roi_bonus

        return dict(scores)

    def get_allocation(self) -> Dict[str, float]:
        """Get recommended allocation percentages per symbol.

        Returns:
            Dict of symbol → allocation fraction (0.0 to 1.0)
            Sum of all values ≤ MAX_PREPOSITION_PCT
        """
        now = time.time()
        if now - self._last_update < self._update_interval and self._symbol_scores:
            return self._symbol_scores

        scores = self._compute_scores()
        self._last_update = now

        if not scores:
            self._symbol_scores = {}
            return {}

        # Filter: minimum signal count
        signal_counts = defaultdict(int)
        for sig in self._signals:
            signal_counts[sig.symbol] += 1

        eligible = {
            sym: score for sym, score in scores.items()
            if signal_counts[sym] >= self.MIN_SIGNALS_FOR_ALLOCATION
        }

        if not eligible:
            self._symbol_scores = {}
            return {}

        # Normalize to allocation fractions
        total_score = sum(eligible.values())
        allocation = {}
        max_coins = self.get_max_preposition_coins()
        for sym, score in sorted(eligible.items(), key=lambda x: -x[1])[:max_coins]:
            frac = (score / total_score) * self.MAX_PREPOSITION_PCT
            frac = min(frac, self.MAX_SINGLE_SYMBOL_PCT)
            allocation[sym] = round(frac, 4)

        # Ensure total doesn't exceed max
        total_alloc = sum(allocation.values())
        if total_alloc > self.MAX_PREPOSITION_PCT:
            scale = self.MAX_PREPOSITION_PCT / total_alloc
            allocation = {k: round(v * scale, 4) for k, v in allocation.items()}

        self._symbol_scores = allocation
        return allocation

    def get_inventory_orders(
        self,
        exchanges: Optional[List[str]] = None
    ) -> List[Dict]:
        """Get specific orders to pre-position inventory on exchanges.

        Returns list of recommended market buy orders to build inventory
        for the hottest trading pairs.

        Args:
            exchanges: List of exchange names to allocate across

        Returns:
            List of order dicts: {exchange, symbol, side, amount_usdt}
        """
        if not self.balance_manager:
            return []

        allocation = self.get_allocation()
        if not allocation:
            return []

        if not exchanges:
            exchanges = list(self.balance_manager.balances.keys())

        orders = []
        for exchange in exchanges:
            usdt_balance = self.balance_manager.get_balance(exchange, 'USDT')
            if usdt_balance < settings.MIN_TRADE_SIZE_USDT * 2:
                continue

            available = usdt_balance - settings.BALANCE_RESERVE_USDT
            if available <= 0:
                continue

            for symbol, frac in allocation.items():
                amount_usdt = available * frac
                if amount_usdt < settings.MIN_TRADE_SIZE_USDT:
                    continue

                # Check if we already have enough of this coin
                # Handle both 'BTC-USDT' and 'BTCUSDT' formats
                base_coin = symbol.split('-')[0] if '-' in symbol else symbol.replace('USDT', '')
                current_holding_usdt = self.balance_manager.get_balance(exchange, base_coin)
                # Skip if already holding equivalent value
                if current_holding_usdt > amount_usdt * 0.5:
                    continue

                orders.append({
                    'exchange': exchange,
                    'symbol': symbol,
                    'side': 'buy',
                    'amount_usdt': round(amount_usdt, 2),
                    'reason': f'Pre-position inventory (score: {frac*100:.1f}%)',
                })

        return orders

    async def execute_rebalance(
        self,
        rest_clients: Optional[Dict] = None,
        price_store=None,
    ) -> List[Dict]:
        """Execute inventory pre-positioning orders.
        
        Autonomously distributes USDT into base coins on each exchange
        based on signal allocation scores. Also sells excess inventory
        that is no longer "hot" back to USDT.
        
        In DRY RUN mode: updates virtual balances only.
        In LIVE mode: places real market orders via REST clients.
        
        Args:
            rest_clients: Dict of {exchange_name: REST_client} for placing orders
            price_store: PriceStore for current prices
            
        Returns:
            List of executed order dicts
        """
        if not self.balance_manager:
            return []
        
        allocation = self.get_allocation()
        if not allocation:
            return []
        
        executed = []
        exchanges = list(self.balance_manager.balances.keys())
        
        for exchange in exchanges:
            usdt_balance = self.balance_manager.get_balance(exchange, 'USDT')
            
            # Keep minimum reserve in USDT (for fees, emergencies)
            reserve = getattr(settings, 'BALANCE_RESERVE_USDT', 2.0)
            available_usdt = usdt_balance - reserve
            if available_usdt < self.MIN_PREPOSITION_USDT:
                continue
            
            # BUY phase: pre-position into "hot" coins
            for symbol, frac in allocation.items():
                target_usdt = available_usdt * frac
                if target_usdt < self.MIN_PREPOSITION_USDT:
                    continue
                
                # Get current holding value in USDT
                base_coin = symbol.split('-')[0] if '-' in symbol else symbol.replace('USDT', '')
                current_amount = self.balance_manager.get_balance(exchange, base_coin)
                
                # Get current price
                price = 0.0
                if price_store:
                    price = self.balance_manager._get_price_from_store(price_store, symbol, exchange)
                    if price <= 0:
                        price = self.balance_manager._get_any_price(price_store, symbol)
                if price <= 0:
                    continue
                
                current_value = current_amount * price
                
                # Buy if we don't have enough of this coin
                if current_value < target_usdt * self.REBALANCE_THRESHOLD_PCT:
                    buy_usdt = min(target_usdt - current_value, available_usdt * self.MAX_SINGLE_BUY_PCT)
                    if buy_usdt < self.MIN_PREPOSITION_USDT:
                        continue
                    
                    buy_qty = buy_usdt / price
                    
                    order = {
                        'exchange': exchange,
                        'symbol': symbol,
                        'side': 'buy',
                        'qty': buy_qty,
                        'price': price,
                        'amount_usdt': round(buy_usdt, 2),
                        'reason': f'Pre-position {base_coin} (alloc: {frac*100:.1f}%)',
                    }
                    
                    if settings.DRY_RUN:
                        # Virtual: update balances directly
                        self.balance_manager.update_balance_optimistic(exchange, 'USDT', -buy_usdt)
                        self.balance_manager.update_balance_optimistic(exchange, base_coin, buy_qty)
                        order['status'] = 'simulated'
                        logger.info(
                            f"🔄 [DRY] {exchange}: Buy {buy_qty:.6g} {base_coin} "
                            f"(${buy_usdt:.2f}) — pre-position"
                        )
                    else:
                        # LIVE: place real market buy
                        client = (rest_clients or {}).get(exchange)
                        if client and hasattr(client, 'place_order'):
                            try:
                                result = await client.place_order(
                                    symbol=symbol,
                                    side='buy',
                                    order_type='market',
                                    quantity=buy_qty,
                                )
                                order['status'] = 'executed'
                                order['result'] = result
                                # Optimistic balance update
                                self.balance_manager.update_balance_optimistic(exchange, 'USDT', -buy_usdt)
                                self.balance_manager.update_balance_optimistic(exchange, base_coin, buy_qty)
                                logger.info(
                                    f"🔄 {exchange}: Bought {buy_qty:.6g} {base_coin} "
                                    f"(${buy_usdt:.2f}) — pre-position"
                                )
                            except Exception as e:
                                order['status'] = 'failed'
                                order['error'] = str(e)
                                logger.warning(f"⚠️ {exchange}: Pre-position buy failed: {e}")
                        else:
                            continue
                    
                    executed.append(order)
                    available_usdt -= buy_usdt
                    if available_usdt < self.MIN_PREPOSITION_USDT:
                        break
            
            # SELL phase: sell coins that are no longer "hot"
            for coin, amount in list(self.balance_manager.balances.get(exchange, {}).items()):
                if coin == 'USDT' or amount <= 0:
                    continue
                
                symbol = f"{coin}-USDT"
                # If this coin is NOT in current allocation, sell it back to USDT
                if symbol not in allocation and amount > 0:
                    price = 0.0
                    if price_store:
                        price = self.balance_manager._get_price_from_store(price_store, symbol, exchange)
                        if price <= 0:
                            price = self.balance_manager._get_any_price(price_store, symbol)
                    if price <= 0:
                        continue
                    
                    sell_value = amount * price
                    if sell_value < self.MIN_PREPOSITION_USDT:
                        continue
                    
                    # Keep a tiny amount for potential arb sells
                    sell_qty = amount * self.LIQUIDATION_PCT
                    sell_usdt = sell_qty * price
                    
                    if sell_usdt < self.MIN_PREPOSITION_USDT:
                        continue
                    
                    order = {
                        'exchange': exchange,
                        'symbol': symbol,
                        'side': 'sell',
                        'qty': sell_qty,
                        'price': price,
                        'amount_usdt': round(sell_usdt, 2),
                        'reason': f'Liquidate {coin} (no longer allocated)',
                    }
                    
                    if settings.DRY_RUN:
                        self.balance_manager.update_balance_optimistic(exchange, coin, -sell_qty)
                        self.balance_manager.update_balance_optimistic(exchange, 'USDT', sell_usdt)
                        order['status'] = 'simulated'
                        logger.info(
                            f"🔄 [DRY] {exchange}: Sell {sell_qty:.6g} {coin} "
                            f"(${sell_usdt:.2f}) — liquidate"
                        )
                    else:
                        client = (rest_clients or {}).get(exchange)
                        if client and hasattr(client, 'place_order'):
                            try:
                                result = await client.place_order(
                                    symbol=symbol,
                                    side='sell',
                                    order_type='market',
                                    quantity=sell_qty,
                                )
                                order['status'] = 'executed'
                                order['result'] = result
                                self.balance_manager.update_balance_optimistic(exchange, coin, -sell_qty)
                                self.balance_manager.update_balance_optimistic(exchange, 'USDT', sell_usdt)
                                logger.info(
                                    f"🔄 {exchange}: Sold {sell_qty:.6g} {coin} "
                                    f"(${sell_usdt:.2f}) — liquidate"
                                )
                            except Exception as e:
                                order['status'] = 'failed'
                                order['error'] = str(e)
                                logger.warning(f"⚠️ {exchange}: Liquidation sell failed: {e}")
                        else:
                            continue
                    
                    executed.append(order)
        
        if executed:
            logger.info(f"📊 Rebalance complete: {len(executed)} orders executed")
        
        return executed

    def get_top_symbols(self, n: int = 5) -> List[Tuple[str, float, int]]:
        """Get top N symbols by signal quality.

        Returns:
            List of (symbol, score, signal_count) tuples, sorted by score desc
        """
        scores = self._compute_scores()
        signal_counts = defaultdict(int)
        for sig in self._signals:
            signal_counts[sig.symbol] += 1

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return [(sym, score, signal_counts[sym]) for sym, score in ranked[:n]]

    def get_summary(self) -> Dict:
        """Get allocation summary for dashboard display."""
        allocation = self.get_allocation()
        top = self.get_top_symbols(5)

        return {
            'total_signals': len(self._signals),
            'unique_symbols': len(set(s.symbol for s in self._signals)),
            'allocation': allocation,
            'top_symbols': [
                {'symbol': sym, 'score': round(score, 2), 'signals': count}
                for sym, score, count in top
            ],
            'max_preposition_pct': self.MAX_PREPOSITION_PCT * 100,
        }

    def has_sufficient_signals(self, min_count: int = 5) -> bool:
        """Check if enough signals have been collected for allocation decisions."""
        return len(self._signals) >= min_count

    def print_summary(self):
        """Print human-readable allocation summary."""
        summary = self.get_summary()
        logger.info("=" * 60)
        logger.info("SIGNAL-BASED CAPITAL ALLOCATION")
        logger.info("=" * 60)
        logger.info(f"Total signals tracked: {summary['total_signals']}")
        logger.info(f"Unique symbols: {summary['unique_symbols']}")
        logger.info(f"Max pre-position: {summary['max_preposition_pct']:.0f}% of idle USDT")

        if summary['top_symbols']:
            logger.info("Top performing symbols:")
            for item in summary['top_symbols']:
                alloc = summary['allocation'].get(item['symbol'], 0) * 100
                logger.info(
                    f"  {item['symbol']:12s} score={item['score']:6.1f} "
                    f"signals={item['signals']:4d} alloc={alloc:5.1f}%"
                )
        else:
            logger.info("  (waiting for signal data...)")
        logger.info("=" * 60)
