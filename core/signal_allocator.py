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
import asyncio
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

    # ========================
    # PRE-FUNDED INVENTORY MODEL
    # ========================
    # How pro arb bots work:
    #   1. Pick the #1 hottest coin (most arb signals)
    #   2. Buy it ONCE on ALL exchanges (one-time setup cost)
    #   3. Arb = just buy on cheap exchange, sell on expensive (2 fees)
    #   4. Natural rebalancing: USDT accumulates on sell-side,
    #      coin accumulates on buy-side — NO extra trades needed
    #   5. Only rotate to a different coin if signals shift dramatically
    #      AND USDT has accumulated enough on the buy-side naturally
    #
    # CRITICAL: With $14/exchange, every extra trade costs ~$0.01-0.03 in fees.
    # JIT/rotation was executing 100+ extra trades → eating ALL profit.

    # Decay half-life in seconds (signals older than this count for less)
    DECAY_HALF_LIFE = 3600.0  # 1 hour

    # Maximum signal history to keep (prevents unbounded memory)
    MAX_HISTORY = 5000

    # Minimum signals before a symbol gets allocation
    MIN_SIGNALS_FOR_ALLOCATION = 3

    # Pre-fund: use 40% of USDT for ONE coin on each exchange
    MAX_PREPOSITION_PCT = 0.40

    # Maximum allocation to any single symbol
    MAX_SINGLE_SYMBOL_PCT = 0.40  # At small capital, focus on 1 coin

    # Minimum order size for pre-positioning
    MIN_PREPOSITION_USDT = 1.0  # $1 minimum

    # CRITICAL: Long cooldowns prevent fee-churning
    REBALANCE_THRESHOLD_PCT = 0.30  # Buy if holding < 30% of target
    MAX_SINGLE_BUY_PCT = 0.50  # Max 50% of available USDT per single buy
    LIQUIDATION_PCT = 0.80  # Sell 80% of non-allocated coins
    REBALANCE_COOLDOWN = 600  # 10 min: prevent fee-churning rotation

    # Weight multiplier for executed trades vs raw signals
    EXECUTED_WEIGHT = 5.0

    # Reactive rebalance: disabled for small capital (causes fee spiral)
    MISS_THRESHOLD = 50  # Effectively disabled: 50 misses before rebalance
    MISS_WINDOW = 300.0  # 5 min window

    # Coin rotation: minimum time before switching to a different coin
    COIN_SWITCH_COOLDOWN = 1800  # 30 minutes before rotating coins
    # Minimum score ratio for new coin to replace current: new must be 3× better
    COIN_SWITCH_RATIO = 3.0

    # Top-up thresholds: when to buy more of current coin on a depleted exchange
    MIN_COIN_PCT_FOR_TOPUP = 0.10  # Coin is <10% of total → depleted
    MIN_USDT_PCT_FOR_TOPUP = 0.80  # USDT is >80% of total → can afford top-up

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
        self._rebalance_history: Dict[tuple, float] = {}  # (exchange, symbol) → last_rebalance_time
        self._total_rebalance_fees = 0.0  # Track total fees spent on rebalancing

        # PRE-FUNDED MODEL: Track the current positioned coin
        # Once positioned, we HOLD it and let arb trades naturally rebalance
        self._current_coin: Optional[str] = None  # e.g. 'NEAR-USDT'
        self._coin_positioned_at: float = 0.0  # timestamp when coin was positioned
        self._initial_setup_done: bool = False  # True after first pre-positioning

        logger.info("✅ SignalAllocator initialized (pre-funded inventory model)")

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
            # Cooldown: max 1 urgent rebalance per 30 seconds per symbol
            last_urgent = self._urgent_symbols.get(symbol, 0)
            if now - last_urgent < 30:
                return  # Already triggered recently, skip spam
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
        exchanges: Optional[List[str]] = None,
        price_store=None
    ) -> List[Dict]:
        """Get specific orders to pre-position inventory on exchanges.

        Returns list of recommended market buy orders to build inventory
        for the hottest trading pairs.

        Args:
            exchanges: List of exchange names to allocate across
            price_store: PriceStore for converting holdings to USDT

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
                current_holding = self.balance_manager.get_balance(exchange, base_coin)
                # Convert holding to USDT (get_balance returns base coin qty, not USDT)
                price = self.balance_manager.get_symbol_price(price_store, symbol, exchange)
                if price <= 0 and current_holding > 0:
                    # Have holdings but no price data — skip to avoid incorrect allocation
                    continue
                current_holding_usdt = current_holding * price if price > 0 else 0
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
        """PRE-FUNDED INVENTORY MODEL — How pro arb bots work.
        
        Phase 1 (INITIAL SETUP — runs once):
          Pick the #1 hottest coin → buy it on ALL exchanges
          Each exchange: 50% USDT + 50% hot coin
          ONE-TIME setup fee: 5 × 0.1% ≈ $0.035
        
        Phase 2 (HOLD — runs every cycle):
          Do NOTHING. Arb trades naturally rebalance inventory:
          - Buy side accumulates base coin, spends USDT
          - Sell side accumulates USDT, spends base coin
          This is FREE — no extra fees!
        
        Phase 3 (COIN SWITCH — rare, only when necessary):
          If current coin has zero signals for 30+ minutes AND
          a new coin has 3× more signals → sell old, buy new.
          Max 1 switch per 30 minutes.
        
        Returns:
            List of executed order dicts
        """
        if not self.balance_manager:
            return []
        
        allocation = self.get_allocation()
        if not allocation:
            return []
        
        now = time.time()
        executed = []
        exchanges = list(self.balance_manager.balances.keys())
        
        # Determine the #1 best coin from signals
        best_coin = max(allocation, key=allocation.get) if allocation else None
        if not best_coin:
            return []
        
        # ========== PHASE 1: INITIAL SETUP (one-time) ==========
        if not self._initial_setup_done:
            self._current_coin = best_coin
            self._coin_positioned_at = now
            self._initial_setup_done = True
            
            base_coin = best_coin.split('-')[0] if '-' in best_coin else best_coin.replace('USDT', '')
            logger.info(
                f"🏦 PRE-FUND SETUP: Positioning {base_coin} on {len(exchanges)} exchanges "
                f"(one-time cost, then pure arb)"
            )
            
            for exchange in exchanges:
                usdt_balance = self.balance_manager.get_balance(exchange, 'USDT')
                reserve = getattr(settings, 'BALANCE_RESERVE_USDT', 2.0)
                available = usdt_balance - reserve
                if available < self.MIN_PREPOSITION_USDT:
                    continue
                
                # Use MAX_PREPOSITION_PCT of available USDT for the coin
                buy_usdt = available * self.MAX_PREPOSITION_PCT
                if buy_usdt < self.MIN_PREPOSITION_USDT:
                    continue
                
                price = 0.0
                if price_store:
                    price = self.balance_manager._get_price_from_store(price_store, best_coin, exchange)
                    if price <= 0:
                        price = self.balance_manager._get_any_price(price_store, best_coin)
                if price <= 0:
                    continue
                
                # Check if already positioned (from previous run)
                current_amount = self.balance_manager.get_balance(exchange, base_coin)
                if current_amount * price > buy_usdt * 0.5:
                    logger.info(f"  ✅ {exchange}: Already has {current_amount:.6g} {base_coin}")
                    continue
                
                buy_qty = buy_usdt / price
                order = await self._execute_buy_order(
                    exchange, best_coin, base_coin, buy_qty, buy_usdt, price,
                    f'Initial pre-fund {base_coin}', rest_clients
                )
                if order:
                    executed.append(order)
            
            if executed:
                logger.info(
                    f"🏦 Pre-fund complete: {base_coin} on {len(executed)}/{len(exchanges)} exchanges. "
                    f"Now pure arb trades — NO more buy/sell overhead!"
                )
            return executed
        
        # ========== PHASE 2: CHECK IF COIN SWITCH NEEDED ==========
        # Only switch if: (1) cooldown passed, (2) current coin has no signals, 
        # (3) new coin is 3× better
        time_since_position = now - self._coin_positioned_at
        
        if time_since_position > self.COIN_SWITCH_COOLDOWN and self._current_coin:
            current_score = allocation.get(self._current_coin, 0.0)
            best_score = allocation.get(best_coin, 0.0)
            
            should_switch = False
            reason = ""
            
            if current_score == 0.0 and best_score > 0:
                # Current coin has zero signals — dead
                should_switch = True
                reason = f"{self._current_coin} has 0 signals, {best_coin} is active"
            elif current_score > 0 and best_score > current_score * self.COIN_SWITCH_RATIO and best_coin != self._current_coin:
                # New coin is dramatically better
                should_switch = True
                reason = f"{best_coin} score {best_score:.2f} > {self.COIN_SWITCH_RATIO}× {self._current_coin} score {current_score:.2f}"
            
            if should_switch:
                old_coin = self._current_coin
                old_base = old_coin.split('-')[0] if '-' in old_coin else old_coin.replace('USDT', '')
                new_base = best_coin.split('-')[0] if '-' in best_coin else best_coin.replace('USDT', '')
                
                logger.info(f"🔄 COIN SWITCH: {old_base} → {new_base} ({reason})")
                
                # Sell old coin on all exchanges
                for exchange in exchanges:
                    amount = self.balance_manager.get_balance(exchange, old_base)
                    if amount <= 0:
                        continue
                    price = 0.0
                    if price_store:
                        price = self.balance_manager._get_price_from_store(price_store, old_coin, exchange)
                        if price <= 0:
                            price = self.balance_manager._get_any_price(price_store, old_coin)
                    if price <= 0:
                        continue
                    
                    sell_usdt = amount * price
                    if sell_usdt < self.MIN_PREPOSITION_USDT:
                        continue
                    
                    sell_qty = amount * self.LIQUIDATION_PCT
                    order = await self._execute_sell_order(
                        exchange, old_coin, old_base, sell_qty, sell_qty * price, price,
                        f'Switch out {old_base}', rest_clients
                    )
                    if order:
                        executed.append(order)
                
                # Buy new coin on all exchanges
                for exchange in exchanges:
                    usdt_balance = self.balance_manager.get_balance(exchange, 'USDT')
                    reserve = getattr(settings, 'BALANCE_RESERVE_USDT', 2.0)
                    available = usdt_balance - reserve
                    if available < self.MIN_PREPOSITION_USDT:
                        continue
                    
                    buy_usdt = available * self.MAX_PREPOSITION_PCT
                    if buy_usdt < self.MIN_PREPOSITION_USDT:
                        continue
                    
                    price = 0.0
                    if price_store:
                        price = self.balance_manager._get_price_from_store(price_store, best_coin, exchange)
                        if price <= 0:
                            price = self.balance_manager._get_any_price(price_store, best_coin)
                    if price <= 0:
                        continue
                    
                    buy_qty = buy_usdt / price
                    order = await self._execute_buy_order(
                        exchange, best_coin, new_base, buy_qty, buy_usdt, price,
                        f'Switch in {new_base}', rest_clients
                    )
                    if order:
                        executed.append(order)
                
                self._current_coin = best_coin
                self._coin_positioned_at = now
                
                if executed:
                    logger.info(f"🔄 Coin switch complete: {old_base} → {new_base} ({len(executed)} orders)")
        
        # ========== PHASE 3: TOP-UP depleted exchanges (rare) ==========
        # If arb trades have depleted coin on one exchange (all sold → only USDT left)
        # AND there's enough USDT accumulated → buy more of the CURRENT coin
        if self._current_coin:
            current_base = self._current_coin.split('-')[0] if '-' in self._current_coin else self._current_coin.replace('USDT', '')
            
            for exchange in exchanges:
                # Cooldown: max 1 top-up per exchange per REBALANCE_COOLDOWN
                rb_key = (exchange, self._current_coin)
                if now - self._rebalance_history.get(rb_key, 0) < self.REBALANCE_COOLDOWN:
                    continue
                
                coin_amount = self.balance_manager.get_balance(exchange, current_base)
                usdt_balance = self.balance_manager.get_balance(exchange, 'USDT')
                
                price = 0.0
                if price_store:
                    price = self.balance_manager._get_price_from_store(price_store, self._current_coin, exchange)
                    if price <= 0:
                        price = self.balance_manager._get_any_price(price_store, self._current_coin)
                if price <= 0:
                    continue
                
                coin_value = coin_amount * price
                total_value = coin_value + usdt_balance
                
                if total_value < self.MIN_PREPOSITION_USDT * 2:
                    continue
                
                # Only top up if coin is nearly depleted (<10% of total) 
                # AND USDT is plentiful (>80% of total)
                coin_pct = coin_value / total_value if total_value > 0 else 0
                if coin_pct < self.MIN_COIN_PCT_FOR_TOPUP and usdt_balance > total_value * self.MIN_USDT_PCT_FOR_TOPUP:
                    # Coin depleted — trades used it all up. Buy more from accumulated USDT
                    reserve = getattr(settings, 'BALANCE_RESERVE_USDT', 2.0)
                    buy_usdt = min(
                        (usdt_balance - reserve) * self.MAX_PREPOSITION_PCT,
                        usdt_balance * self.MAX_PREPOSITION_PCT
                    )
                    if buy_usdt < self.MIN_PREPOSITION_USDT:
                        continue
                    
                    buy_qty = buy_usdt / price
                    order = await self._execute_buy_order(
                        exchange, self._current_coin, current_base, buy_qty, buy_usdt, price,
                        f'Top-up {current_base} (depleted by arb trades)', rest_clients
                    )
                    if order:
                        executed.append(order)
        
        # Sync real balances after rebalance
        if executed and not settings.DRY_RUN and self.balance_manager and rest_clients:
            await asyncio.sleep(1.0)
            for name, client in rest_clients.items():
                try:
                    await self.balance_manager._fetch_balance(name, client)
                except Exception as e:
                    logger.debug(f"Post-rebalance sync {name}: {e}")
        
        return executed

    async def _execute_buy_order(
        self, exchange: str, symbol: str, base_coin: str,
        qty: float, usdt_amount: float, price: float,
        reason: str, rest_clients: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Execute a buy order (used by pre-fund, top-up, and coin switch)."""
        from core.exchange_config import EXCHANGE_PARAMS
        fee_rate = EXCHANGE_PARAMS.get(exchange, {}).get('taker', 0.001)
        
        order = {
            'exchange': exchange, 'symbol': symbol, 'side': 'buy',
            'qty': qty, 'price': price, 'amount_usdt': round(usdt_amount, 2),
            'reason': reason,
        }
        
        if settings.DRY_RUN:
            fee_cost = usdt_amount * fee_rate
            qty_after_fee = qty * (1.0 - fee_rate)
            self.balance_manager.update_balance_optimistic(exchange, 'USDT', -usdt_amount)
            self.balance_manager.update_balance_optimistic(exchange, base_coin, qty_after_fee)
            self._total_rebalance_fees += fee_cost
            self._rebalance_history[(exchange, symbol)] = time.time()
            order['status'] = 'simulated'
            logger.info(
                f"  🏦 [DRY] {exchange}: Buy {qty_after_fee:.6g} {base_coin} "
                f"(${usdt_amount:.2f}, fee=${fee_cost:.4f}) — {reason}"
            )
            return order
        else:
            client = (rest_clients or {}).get(exchange)
            if not client or not hasattr(client, 'place_order'):
                return None
            try:
                result = await client.place_order(
                    symbol=symbol, side='buy', order_type='market', quantity=qty,
                )
                self._rebalance_history[(exchange, symbol)] = time.time()
                self.balance_manager.update_balance_optimistic(exchange, 'USDT', -usdt_amount)
                self.balance_manager.update_balance_optimistic(exchange, base_coin, qty)
                order['status'] = 'executed'
                order['result'] = result
                logger.info(f"  🏦 {exchange}: Bought {qty:.6g} {base_coin} (${usdt_amount:.2f}) — {reason}")
                return order
            except Exception as e:
                logger.warning(f"⚠️ {exchange}: Buy failed: {e}")
                return None

    async def _execute_sell_order(
        self, exchange: str, symbol: str, base_coin: str,
        qty: float, usdt_amount: float, price: float,
        reason: str, rest_clients: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Execute a sell order (used by coin switch only)."""
        from core.exchange_config import EXCHANGE_PARAMS
        fee_rate = EXCHANGE_PARAMS.get(exchange, {}).get('taker', 0.001)
        
        order = {
            'exchange': exchange, 'symbol': symbol, 'side': 'sell',
            'qty': qty, 'price': price, 'amount_usdt': round(usdt_amount, 2),
            'reason': reason,
        }
        
        if settings.DRY_RUN:
            fee_cost = usdt_amount * fee_rate
            usdt_after_fee = usdt_amount * (1.0 - fee_rate)
            self.balance_manager.update_balance_optimistic(exchange, base_coin, -qty)
            self.balance_manager.update_balance_optimistic(exchange, 'USDT', usdt_after_fee)
            self._total_rebalance_fees += fee_cost
            self._rebalance_history[(exchange, symbol)] = time.time()
            order['status'] = 'simulated'
            logger.info(
                f"  🔄 [DRY] {exchange}: Sell {qty:.6g} {base_coin} "
                f"(${usdt_after_fee:.2f} after fee=${fee_cost:.4f}) — {reason}"
            )
            return order
        else:
            client = (rest_clients or {}).get(exchange)
            if not client or not hasattr(client, 'place_order'):
                return None
            try:
                result = await client.place_order(
                    symbol=symbol, side='sell', order_type='market', quantity=qty,
                )
                self._rebalance_history[(exchange, symbol)] = time.time()
                self.balance_manager.update_balance_optimistic(exchange, base_coin, -qty)
                self.balance_manager.update_balance_optimistic(exchange, 'USDT', usdt_amount)
                order['status'] = 'executed'
                order['result'] = result
                logger.info(f"  🔄 {exchange}: Sold {qty:.6g} {base_coin} (${usdt_amount:.2f}) — {reason}")
                return order
            except Exception as e:
                logger.warning(f"⚠️ {exchange}: Sell failed: {e}")
                return None

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
