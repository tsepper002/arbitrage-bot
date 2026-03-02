#!/usr/bin/env python3
"""
Order execution layer with dry_run and live modes.
Provides a safe interface for order placement with detailed logging.
Enhanced with parallel order execution and balance integration.
"""
import time
import asyncio
import logging
from collections import deque
from typing import List, Optional, Tuple, Dict
from datetime import datetime
import settings

logger = logging.getLogger("order_executor")


class OrderExecutor:
    """
    Handles order execution with two modes:
    - dry_run (default): Simulates orders, logs actions without sending to exchanges
    - live: Real order placement with parallel execution and balance management
    """
    
    def __init__(self, dry_run: Optional[bool] = None, rest_clients: Optional[Dict] = None, balance_manager=None, capital_manager=None):
        """
        Initialize order executor.
        
        Args:
            dry_run: If True, simulate orders. If None, uses settings.DRY_RUN
            rest_clients: Dict of {exchange_name: REST_client} for live trading
            balance_manager: BalanceManager instance for balance tracking
            capital_manager: CapitalManager instance for Engine 2.0 kill-logic + quality ranking
        """
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        self.rest_clients = rest_clients or {}
        self.balance_manager = balance_manager
        self.capital_manager = capital_manager
        self.order_history: deque = deque(maxlen=10000)  # Auto-bounded
        self.trade_count_per_minute: Dict[int, int] = {}  # minute timestamp -> count
        self.last_trade_time_per_symbol: Dict[str, float] = {}  # symbol -> last trade timestamp
        self._trade_lock = asyncio.Lock()  # Prevent concurrent trade execution
        self._blocked_cooldown: Dict[str, float] = {}  # symbol → last blocked time
        self.BLOCKED_COOLDOWN_SEC = 10.0  # Don't retry blocked trades for 10s
        
        if self.dry_run:
            logger.info("🔵 OrderExecutor initialized in DRY RUN mode (safe simulation)")
        else:
            if not self.rest_clients:
                logger.warning("⚠️  LIVE mode enabled but no REST clients provided!")
            logger.warning("🔴 OrderExecutor initialized in LIVE mode - REAL ORDERS WILL BE PLACED!")
    
    def can_trade(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """
        Check if trading is allowed based on rate limits, cooldowns, and blocked status.
        
        Returns:
            (can_trade, reason) tuple — True/None if allowed, False/reason if blocked.
        """
        current_time = time.time()
        current_minute = int(current_time / 60)
        
        # Check per-minute rate limit
        trades_this_minute = self.trade_count_per_minute.get(current_minute, 0)
        if trades_this_minute >= settings.MAX_TRADES_PER_MINUTE:
            return False, f"Rate limit: {trades_this_minute} trades this minute (max: {settings.MAX_TRADES_PER_MINUTE})"
        
        # Check per-symbol cooldown
        last_trade_time = self.last_trade_time_per_symbol.get(symbol, 0)
        time_since_last = current_time - last_trade_time
        if time_since_last < settings.PER_SYMBOL_COOLDOWN_SEC:
            remaining = settings.PER_SYMBOL_COOLDOWN_SEC - time_since_last
            return False, f"Symbol cooldown: {remaining:.1f}s remaining (cooldown: {settings.PER_SYMBOL_COOLDOWN_SEC}s)"
        
        # Check blocked cooldown (prevents spamming failed trades)
        last_blocked = self._blocked_cooldown.get(symbol, 0)
        if current_time - last_blocked < self.BLOCKED_COOLDOWN_SEC:
            return False, f"Blocked cooldown: {max(0, self.BLOCKED_COOLDOWN_SEC - (current_time - last_blocked)):.0f}s"
        
        return True, None
    
    def _record_trade(self, symbol: str, order_info: Dict):
        """Record trade for rate limiting and history."""
        current_time = time.time()
        current_minute = int(current_time / 60)
        
        # Update rate limit counter
        self.trade_count_per_minute[current_minute] = self.trade_count_per_minute.get(current_minute, 0) + 1
        
        # Update per-symbol cooldown
        self.last_trade_time_per_symbol[symbol] = current_time
        
        # Store in history
        order_info['executed_at'] = current_time
        order_info['executed_at_iso'] = datetime.fromtimestamp(current_time).isoformat()
        self.order_history.append(order_info)
        
        # Clean old minute counters (keep last 5 minutes)
        old_minutes = [m for m in self.trade_count_per_minute.keys() if m < current_minute - 5]
        for m in old_minutes:
            del self.trade_count_per_minute[m]
    
    async def execute_arbitrage(self, opportunity: Dict) -> Dict:
        """
        Execute an arbitrage opportunity.
        Uses asyncio.Lock to prevent concurrent trade execution — only one
        trade at a time across ALL callers (engine + strategy dispatcher).
        """
        symbol = opportunity['symbol']
        
        # Check if trade is allowed
        can_trade, reason = self.can_trade(symbol)
        if not can_trade:
            logger.debug(f"Trade blocked for {symbol}: {reason}")
            return {
                'status': 'blocked',
                'reason': reason,
                'opportunity': opportunity
            }
        
        # Serialize all trade execution through a single lock
        async with self._trade_lock:
            if self.dry_run:
                return self._execute_dry_run(opportunity)
            else:
                return await self._execute_live(opportunity)
    
    def _execute_dry_run(self, opp: Dict) -> Dict:
        """Simulate order execution with realistic balance tracking.
        
        In dry-run mode, virtual balances are updated to reflect the trade:
        - Buy side: USDT decreases, base coin increases
        - Sell side: base coin decreases, USDT increases
        
        This ensures realistic simulation where:
        - Trades can't happen without sufficient USDT on buy exchange
        - Trades can't happen without pre-positioned base coin on sell exchange
        - Capital depletion is tracked accurately
        """
        symbol = opp['symbol']
        buy_ex = opp['buy_ex']
        sell_ex = opp['sell_ex']
        qty = opp['qty']
        buy_price = opp['buy_avg']
        sell_price = opp['sell_avg']
        net_profit = opp['net']
        roi_pct = opp['roi_pct']
        
        # Parse currencies
        base_currency = symbol.split('-')[0] if '-' in symbol else symbol.replace('USDT', '')
        quote_currency = 'USDT'
        
        # PROFIT GATE (same as live mode for consistent simulation)
        if net_profit < (self.MIN_LIVE_NET_PROFIT - self.PROFIT_TOLERANCE) and net_profit >= 0:
            logger.debug(f"[DRY] ⛔ {symbol}: Profit ${net_profit:.4f} < ${self.MIN_LIVE_NET_PROFIT} minimum")
            return {'status': 'blocked', 'reason': f'Too thin: ${net_profit:.4f} < ${self.MIN_LIVE_NET_PROFIT}'}
        
        # Check virtual balances before executing (realistic simulation)
        if self.balance_manager:
            # Fee buffer: max taker fee is 0.2% (HTX), round up to 0.2% for safety
            FEE_BUFFER = 1.002
            # Use lower min order in dry-run since no exchange API call
            min_order = 1.0
            
            # Auto-adjust qty to available balance (prevents precision rounding issues)
            available_sell = self.balance_manager.get_balance(sell_ex, base_currency)
            available_buy_usdt = self.balance_manager.get_balance(buy_ex, quote_currency)
            max_qty_from_usdt = available_buy_usdt / (buy_price * FEE_BUFFER) if buy_price > 0 else 0
            
            # Use the minimum of requested qty, available to sell, and available to buy
            adjusted_qty = min(qty, available_sell, max_qty_from_usdt)
            
            if adjusted_qty <= 0 or (adjusted_qty * buy_price) < min_order:
                # Not enough balance for any meaningful trade
                if available_sell <= 0:
                    self._blocked_cooldown[symbol] = time.time()
                    return {
                        'status': 'blocked',
                        'reason': f'No {base_currency} on {sell_ex}: have {available_sell:.6f}',
                        'missed_symbol': symbol,
                        'missed_exchange': sell_ex,
                        'missed_side': 'sell',
                    }
                else:
                    self._blocked_cooldown[symbol] = time.time()
                    return {
                        'status': 'blocked',
                        'reason': f'Insufficient USDT on {buy_ex}: have ${available_buy_usdt:.2f}',
                        'missed_symbol': symbol,
                        'missed_exchange': buy_ex,
                        'missed_side': 'buy',
                    }
            
            # Update qty and recalculate profit if adjusted
            if adjusted_qty < qty * self.QTY_ADJUST_THRESHOLD:
                ratio = adjusted_qty / qty
                qty = adjusted_qty
                net_profit = net_profit * ratio
                logger.debug(f"[DRY] Adjusted qty to {qty:.6f} ({ratio:.1%} of requested) based on balance")
        
        logger.info(
            f"💰 [DRY RUN] ARBITRAGE OPPORTUNITY DETECTED\n"
            f"   Symbol: {symbol}\n"
            f"   Buy:  {qty:.6f} @ ${buy_price:.6f} on {buy_ex} (cost: ${qty * buy_price:.2f})\n"
            f"   Sell: {qty:.6f} @ ${sell_price:.6f} on {sell_ex} (receive: ${qty * sell_price:.2f})\n"
            f"   Net Profit: ${net_profit:.4f} ({roi_pct:.3f}% ROI)"
        )
        
        # Update virtual balances (realistic simulation)
        if self.balance_manager:
            buy_cost_actual = qty * buy_price
            sell_proceeds = qty * sell_price
            self.balance_manager.record_trade(
                buy_ex, sell_ex, base_currency, quote_currency,
                qty, buy_cost_actual, sell_proceeds
            )
        
        # Record simulated trade
        order_info = {
            'mode': 'dry_run',
            'symbol': symbol,
            'buy_exchange': buy_ex,
            'sell_exchange': sell_ex,
            'quantity': qty,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'net_profit': net_profit,
            'roi_pct': roi_pct,
            'buy_order_id': f"DRY_{int(time.time())}_{buy_ex}",
            'sell_order_id': f"DRY_{int(time.time())}_{sell_ex}",
        }
        
        self._record_trade(symbol, order_info)
        
        # Engine 2.0: Report to CapitalManager (works in dry-run too for kill-logic testing)
        if self.capital_manager:
            self.capital_manager.record_trade_result(
                symbol=symbol,
                buy_exchange=buy_ex,
                sell_exchange=sell_ex,
                net_profit_pct=roi_pct,
                slippage_pct=0.0,  # No slippage in dry-run
            )
        
        return {
            'status': 'simulated',
            'trade_info': order_info,
            'message': 'Orders simulated successfully (dry run mode)'
        }
    
    # Maximum time to wait for order fill confirmation
    FILL_TIMEOUT_SEC = 10.0
    # Poll interval for checking order status
    FILL_POLL_INTERVAL = 0.5
    # Maximum allowed slippage vs expected price (per leg)
    MAX_SLIPPAGE_PCT = 0.2  # 0.2% max deviation — tight to protect thin arb spreads
    # Minimum order size in USDT to avoid exchange rejections
    MIN_ORDER_USDT = 5.0  # All 5 exchanges require ≥$5 notional
    # Minimum expected net profit to execute a LIVE trade
    # Set to $0.01 — lower than previous $0.02 because the hard fee floor in
    # _build_trade_from_signal already ensures spread > fees. This gate catches
    # edge cases where qty adjustment reduces expected profit after fee validation.
    MIN_LIVE_NET_PROFIT = 0.01
    # Floating-point tolerance for profit comparisons (prevents rejecting
    # trades that are exactly at the threshold due to IEEE 754 rounding)
    PROFIT_TOLERANCE = 0.001
    # Minimum ROI % to execute a LIVE trade — catches cases where net profit
    # passes the dollar gate but percentage is essentially zero (e.g., very large qty)
    MIN_LIVE_ROI_PCT = 0.01
    # Minimum ratio of adjusted qty vs requested qty to proceed
    QTY_ADJUST_THRESHOLD = 0.95  # Proceed if ≥95% of requested qty available

    async def _execute_live(self, opp: Dict) -> Dict:
        """
        Execute live arbitrage with PARALLEL order placement and fill verification.
        
        Strategy:
        0. Verify expected profit is worth the risk (protects against slippage)
        1. Check balances and auto-adjust qty to available
        2. Place buy and sell orders SIMULTANEOUSLY
        3. VERIFY both orders filled (poll order status)
        4. Check slippage vs expected price
        5. If one fails, emergency close the other
        6. Sync real balances from exchange
        """
        symbol = opp['symbol']
        buy_ex = opp['buy_ex']
        sell_ex = opp['sell_ex']
        qty = opp['qty']
        buy_price = opp.get('buy_avg', opp.get('buy_price'))
        sell_price = opp.get('sell_avg', opp.get('sell_price'))
        expected_net = opp.get('net')
        expected_roi = opp.get('roi_pct')
        
        base_currency = symbol.split('-')[0]
        quote_currency = symbol.split('-')[1] if '-' in symbol else 'USDT'
        
        # Step 0: PROFIT GATE — refuse trades that are too thin for live execution
        # Live has slippage, delays, and fill uncertainty. Need sufficient margin.
        if expected_net is None or expected_roi is None:
            return {'status': 'blocked', 'reason': 'Missing net/roi_pct in opportunity — cannot verify profitability'}
        if expected_net < self.MIN_LIVE_NET_PROFIT:
            reason = (f"Expected profit ${expected_net:.4f} < ${self.MIN_LIVE_NET_PROFIT} minimum "
                      f"(ROI={expected_roi:.3f}%) — too thin for live execution")
            logger.debug(f"⛔ {symbol}: {reason}")
            return {'status': 'blocked', 'reason': reason}
        if expected_roi < self.MIN_LIVE_ROI_PCT:
            reason = (f"Expected ROI {expected_roi:.3f}% < {self.MIN_LIVE_ROI_PCT}% minimum "
                      f"(net=${expected_net:.4f}) — slippage would likely eat profit")
            logger.debug(f"⛔ {symbol}: {reason}")
            return {'status': 'blocked', 'reason': reason}
        
        # EXPOSURE CAPS: per-exchange AND per-coin limits
        if self.balance_manager:
            total_capital = sum(
                self.balance_manager.get_balance(ex, 'USDT')
                for ex in self.balance_manager.balances.keys()
            )
            if total_capital <= 0:
                logger.warning("⚠️  Exposure cap: total USDT capital is 0 — balance manager may not be initialized")
                total_capital = 1.0
            trade_value = qty * buy_price
            
            # Per-exchange cap
            max_per_exchange = total_capital * (settings.MAX_EXPOSURE_PER_EXCHANGE_PCT / 100.0)
            if trade_value > max_per_exchange:
                old_qty = qty
                qty = max_per_exchange / buy_price if buy_price > 0 else 0
                trade_value = qty * buy_price
                if trade_value < self.MIN_ORDER_USDT:
                    return {'status': 'blocked', 'reason': f'Exposure cap: would exceed {settings.MAX_EXPOSURE_PER_EXCHANGE_PCT}% on {buy_ex}'}
                logger.info(f"📏 Exchange cap: {old_qty:.6f} → {qty:.6f} ({settings.MAX_EXPOSURE_PER_EXCHANGE_PCT}% limit)")
            
            # Per-coin cap: total exposure to this coin across ALL exchanges
            # Handle symbol formats: "BTC-USDT", "BTC/USDT", "BTCUSDT"
            base_coin = symbol.split('-')[0] if '-' in symbol else symbol.split('/')[0] if '/' in symbol else symbol.replace('USDT', '')
            coin_exposure = sum(
                self.balance_manager.get_balance(ex, base_coin) * buy_price  # Use buy_price as approximate valuation
                for ex in self.balance_manager.balances.keys()
            )
            max_per_coin = total_capital * (settings.MAX_EXPOSURE_PER_COIN_PCT / 100.0)
            if coin_exposure + trade_value > max_per_coin:
                allowed_value = max(0, max_per_coin - coin_exposure)
                if allowed_value < self.MIN_ORDER_USDT:
                    return {'status': 'blocked', 'reason': f'Coin exposure cap: {base_coin} at ${coin_exposure:.2f} ({coin_exposure/total_capital*100:.1f}% of {settings.MAX_EXPOSURE_PER_COIN_PCT}% max)'}
                old_qty = qty
                qty = allowed_value / buy_price if buy_price > 0 else 0
                logger.info(f"📏 Coin cap: {old_qty:.6f} → {qty:.6f} ({base_coin} at {coin_exposure/total_capital*100:.1f}% exposure)")

        logger.info(
            f"🔴 LIVE EXECUTION: {symbol} | "
            f"Buy {qty} @ ${buy_price:.4f} on {buy_ex} | "
            f"Sell {qty} @ ${sell_price:.4f} on {sell_ex} | "
            f"Expected: ${expected_net:.4f} ({expected_roi:.3f}%)"
        )
        
        try:
            # Step 1: Get REST clients
            buy_client = self.rest_clients.get(buy_ex)
            sell_client = self.rest_clients.get(sell_ex)
            
            if not buy_client or not sell_client:
                error_msg = f"Missing REST client: {buy_ex if not buy_client else sell_ex}"
                logger.error(f"❌ {error_msg}")
                return {'status': 'error', 'reason': error_msg}
            
            # Step 2: Auto-adjust qty to available balance (with fee buffer)
            if self.balance_manager:
                # Use has_sufficient_balance for proper safety margin checks
                available_usdt = self.balance_manager.get_balance(buy_ex, quote_currency)
                available_base = self.balance_manager.get_balance(sell_ex, base_currency)
                # Fee buffer: 0.3% covers max taker fee (HTX 0.2%) + slippage
                FEE_BUFFER = 1.003
                max_qty_buy = available_usdt / (buy_price * FEE_BUFFER) if buy_price > 0 else 0
                adjusted_qty = min(qty, available_base, max_qty_buy)
                
                if adjusted_qty <= 0 or adjusted_qty * buy_price < self.MIN_ORDER_USDT:
                    reason = (f"Insufficient balance: {buy_ex} USDT=${available_usdt:.2f}, "
                              f"{sell_ex} {base_currency}={available_base:.6f}")
                    logger.warning(f"⚠️  {reason}")
                    # Set blocked cooldown to prevent spamming this symbol
                    self._blocked_cooldown[symbol] = time.time()
                    return {
                        'status': 'blocked', 'reason': reason,
                        'missed_symbol': symbol, 'missed_exchange': sell_ex,
                        'missed_side': 'sell' if available_base < adjusted_qty else 'buy',
                    }
                
                if adjusted_qty < qty * self.QTY_ADJUST_THRESHOLD:
                    logger.info(f"📏 Adjusted qty: {qty:.6f} → {adjusted_qty:.6f} (balance limited)")
                    qty = adjusted_qty
            
            # Step 3: Place orders — Maker-First model or Parallel Market orders
            # Engine 2.0: Maker-First reduces fees by using limit buy + market sell
            # (saves 0.05-0.10% on buy side = significant for thin spreads)
            logger.info(f"⚡ Placing PARALLEL orders: Buy {qty:.6f} on {buy_ex}, Sell on {sell_ex}")
            start_time = time.time()
            
            use_maker_first = (
                settings.MAKER_FIRST_ENABLED
                and not self.dry_run
                and buy_price and sell_price
                and sell_price > buy_price
            )
            
            if use_maker_first:
                # Maker-first: limit buy, wait for fill, THEN market sell
                spread = sell_price - buy_price
                maker_buy_price = buy_price + spread * (settings.MAKER_PRICE_OFFSET_PCT / 100.0)
                
                # Place limit buy first
                buy_result = await buy_client.place_order(symbol, 'buy', 'limit', qty, maker_buy_price)
                if isinstance(buy_result, Exception):
                    logger.error(f"❌ Maker buy failed: {buy_result}")
                    return {'status': 'error', 'reason': f'Maker buy failed: {buy_result}'}
                
                # Wait for fill (up to MAKER_FILL_TIMEOUT_MS)
                buy_order_id = self._extract_order_id(buy_result)
                fill_timeout_sec = settings.MAKER_FILL_TIMEOUT_MS / 1000.0
                buy_fill = await self._verify_fill(buy_client, symbol, buy_order_id, 'buy', maker_buy_price, qty)
                buy_filled_pct = (buy_fill.get('filled_qty', 0) / qty * 100) if qty > 0 else 0
                
                if buy_filled_pct < settings.MAKER_MIN_FILL_PCT:
                    # Not enough fill — cancel and abort
                    await self._safe_cancel(buy_client, symbol, buy_order_id, 'buy')
                    logger.info(f"📭 Maker buy only {buy_filled_pct:.0f}% filled (need {settings.MAKER_MIN_FILL_PCT}%) — cancelled")
                    return {'status': 'blocked', 'reason': f'Maker buy fill too low: {buy_filled_pct:.0f}%'}
                
                # Buy filled ≥ min_fill_pct → place market sell
                sell_qty = buy_fill.get('filled_qty', qty)
                sell_result = await sell_client.place_order(symbol, 'sell', 'market', sell_qty, sell_price)
                if isinstance(sell_result, Exception):
                    logger.error(f"❌ Sell after maker buy failed: {sell_result}")
                    await self._emergency_close(buy_ex, symbol, 'sell', sell_qty, sell_price, buy_client)
                    return {'status': 'error', 'reason': f'Sell after maker buy failed: {sell_result}'}
                
                buy_result_final = buy_result
                sell_result_final = sell_result
            else:
                # Standard parallel market orders
                buy_task = buy_client.place_order(symbol, 'buy', 'market', qty, buy_price)
                sell_task = sell_client.place_order(symbol, 'sell', 'market', qty, sell_price)
                results = await asyncio.gather(buy_task, sell_task, return_exceptions=True)
                buy_result_final, sell_result_final = results
            
            results = [buy_result_final, sell_result_final]
            buy_result, sell_result = results
            placement_time = time.time() - start_time
            
            # Step 4: Handle placement failures
            if isinstance(buy_result, Exception):
                logger.error(f"❌ Buy order failed: {buy_result}")
                if not isinstance(sell_result, Exception):
                    sell_oid = self._extract_order_id(sell_result)
                    logger.warning(f"⚠️  EMERGENCY: Sell placed (id={sell_oid}) but buy failed — reversing...")
                    await self._emergency_close(sell_ex, symbol, 'buy', qty, buy_price, sell_client)
                return {'status': 'error', 'reason': f'Buy placement failed: {buy_result}'}
            
            if isinstance(sell_result, Exception):
                logger.error(f"❌ Sell order failed: {sell_result}")
                buy_oid = self._extract_order_id(buy_result)
                logger.warning(f"⚠️  EMERGENCY: Buy placed (id={buy_oid}) but sell failed — reversing...")
                await self._emergency_close(buy_ex, symbol, 'sell', qty, sell_price, buy_client)
                return {'status': 'error', 'reason': f'Sell placement failed: {sell_result}'}
            
            # Step 5: Extract order IDs and verify fills
            buy_order_id = self._extract_order_id(buy_result)
            sell_order_id = self._extract_order_id(sell_result)
            
            logger.info(f"📋 Orders placed in {placement_time:.3f}s: buy={buy_order_id}, sell={sell_order_id}")
            
            # Verify fills (poll order status)
            buy_fill = await self._verify_fill(buy_client, symbol, buy_order_id, 'buy', buy_price, qty)
            sell_fill = await self._verify_fill(sell_client, symbol, sell_order_id, 'sell', sell_price, qty)
            
            execution_time = time.time() - start_time
            
            # Step 6: Check fill results and handle partial fills
            buy_filled_qty = buy_fill.get('filled_qty', 0) if buy_fill.get('filled') else 0
            sell_filled_qty = sell_fill.get('filled_qty', 0) if sell_fill.get('filled') else 0
            
            if buy_filled_qty == 0 and sell_filled_qty == 0:
                logger.error(f"❌ BOTH orders unfilled after {self.FILL_TIMEOUT_SEC}s — no action needed")
                if buy_order_id:
                    await self._safe_cancel(buy_client, symbol, buy_order_id, 'buy')
                if sell_order_id:
                    await self._safe_cancel(sell_client, symbol, sell_order_id, 'sell')
                return {'status': 'error', 'reason': 'Both orders unfilled'}
            
            # Check for partial fill imbalance
            if buy_filled_qty > 0 and sell_filled_qty > 0:
                max_filled = max(buy_filled_qty, sell_filled_qty)
                if max_filled < 1e-8:
                    return {'status': 'error', 'reason': 'Near-zero fill quantities'}
                fill_ratio = min(buy_filled_qty, sell_filled_qty) / max_filled
                if fill_ratio < 0.95:  # >5% imbalance
                    excess_side = 'buy' if buy_filled_qty > sell_filled_qty else 'sell'
                    excess_qty = abs(buy_filled_qty - sell_filled_qty)
                    logger.warning(
                        f"⚠️ Partial fill imbalance: buy={buy_filled_qty:.6f}, sell={sell_filled_qty:.6f} "
                        f"({excess_side} excess: {excess_qty:.6f})"
                    )
                    # Hedge the excess by placing an offsetting order
                    if excess_side == 'buy':
                        # We bought more than we sold — sell the excess
                        await self._emergency_close(buy_ex, symbol, 'sell', excess_qty, sell_price, buy_client)
                    else:
                        # We sold more than we bought — buy back the excess
                        await self._emergency_close(sell_ex, symbol, 'buy', excess_qty, buy_price, sell_client)
            elif buy_filled_qty > 0 and sell_filled_qty == 0:
                logger.error(f"❌ Buy filled ({buy_filled_qty:.6f}) but sell NOT filled — reversing")
                if sell_order_id:
                    await self._safe_cancel(sell_client, symbol, sell_order_id, 'sell')
                await self._emergency_close(buy_ex, symbol, 'sell', buy_filled_qty, sell_price, buy_client)
                return {'status': 'error', 'reason': 'Sell not filled, reversed buy'}
            elif sell_filled_qty > 0 and buy_filled_qty == 0:
                logger.error(f"❌ Sell filled ({sell_filled_qty:.6f}) but buy NOT filled — reversing")
                if buy_order_id:
                    await self._safe_cancel(buy_client, symbol, buy_order_id, 'buy')
                await self._emergency_close(sell_ex, symbol, 'buy', sell_filled_qty, buy_price, sell_client)
                return {'status': 'error', 'reason': 'Buy not filled, reversed sell'}
            
            # Step 7: Check slippage
            actual_buy_price = buy_fill.get('avg_price', buy_price)
            actual_sell_price = sell_fill.get('avg_price', sell_price)
            buy_slippage = abs(actual_buy_price - buy_price) / buy_price * 100 if buy_price > 0 else 0
            sell_slippage = abs(actual_sell_price - sell_price) / sell_price * 100 if sell_price > 0 else 0
            
            if buy_slippage > self.MAX_SLIPPAGE_PCT or sell_slippage > self.MAX_SLIPPAGE_PCT:
                logger.warning(
                    f"⚠️  Slippage: buy {buy_slippage:.2f}% (${buy_price:.4f}→${actual_buy_price:.4f}), "
                    f"sell {sell_slippage:.2f}% (${sell_price:.4f}→${actual_sell_price:.4f})"
                )
            
            # Step 8: Calculate real profit (from actual fill prices)
            actual_qty = min(buy_fill.get('filled_qty', qty), sell_fill.get('filled_qty', qty))
            actual_profit = (actual_sell_price - actual_buy_price) * actual_qty
            actual_roi = (actual_sell_price / actual_buy_price - 1) * 100 if actual_buy_price > 0 else 0
            
            logger.info(f"✅ BOTH FILLED in {execution_time:.3f}s | Profit: ${actual_profit:.4f} ({actual_roi:.3f}%)")
            
            # Step 9: Update balances from actual fills (not estimates)
            if self.balance_manager:
                self.balance_manager.record_trade(
                    buy_ex, sell_ex, base_currency, quote_currency,
                    actual_qty, actual_qty * actual_buy_price, actual_qty * actual_sell_price
                )
                # Force immediate balance sync after trade (fire-and-forget with error handling)
                task = asyncio.create_task(self._sync_balances_after_trade(buy_client, sell_client, buy_ex, sell_ex))
                task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.exception() else None)
            
            # Step 10: Record trade with ACTUAL values
            trade_info = {
                'symbol': symbol,
                'buy_ex': buy_ex,
                'sell_ex': sell_ex,
                'qty': actual_qty,
                'buy_price': actual_buy_price,
                'sell_price': actual_sell_price,
                'buy_order_id': buy_order_id,
                'sell_order_id': sell_order_id,
                'net_profit': actual_profit,
                'roi_pct': actual_roi,
                'execution_time_sec': execution_time,
                'buy_slippage_pct': buy_slippage,
                'sell_slippage_pct': sell_slippage,
                'mode': 'LIVE'
            }
            
            self._record_trade(symbol, trade_info)
            
            # Engine 2.0: Report to CapitalManager for kill-logic + quality ranking
            if self.capital_manager:
                max_slippage = max(buy_slippage, sell_slippage)
                self.capital_manager.record_trade_result(
                    symbol=symbol,
                    buy_exchange=buy_ex,
                    sell_exchange=sell_ex,
                    net_profit_pct=actual_roi,
                    slippage_pct=max_slippage,
                )
            
            logger.info(
                f"💰 LIVE TRADE COMPLETED: {symbol} "
                f"${actual_profit:.4f} profit ({actual_roi:.3f}% ROI) "
                f"in {execution_time:.3f}s"
            )
            
            return {'status': 'success', 'trade_info': trade_info}
            
        except Exception as e:
            logger.exception(f"❌ Live execution failed: {e}")
            return {'status': 'error', 'reason': str(e)}
    
    def _extract_order_id(self, result: Dict) -> str:
        """Extract order ID from any exchange's response format."""
        if not isinstance(result, dict):
            return str(result)
        # Try all known field names across exchanges
        for key in ('orderId', 'order_id', 'orderLinkId', 'id', 'clientOid'):
            val = result.get(key)
            if val:
                return str(val)
        # Nested: Bybit puts it in result.result.orderId
        nested = result.get('result', {})
        if isinstance(nested, dict):
            for key in ('orderId', 'order_id'):
                val = nested.get(key)
                if val:
                    return str(val)
        # KuCoin: data.orderId
        data = result.get('data', {})
        if isinstance(data, dict):
            for key in ('orderId', 'order_id'):
                val = data.get(key)
                if val:
                    return str(val)
        return ""
    
    async def _verify_fill(self, client, symbol: str, order_id: str, side: str, expected_price: float, expected_qty: float = 0) -> Dict:
        """Poll order status until filled or timeout."""
        if not order_id or not hasattr(client, 'get_order_status'):
            # Can't verify — assume filled at expected values
            return {'filled': True, 'avg_price': expected_price, 'filled_qty': expected_qty}
        
        deadline = time.time() + self.FILL_TIMEOUT_SEC
        while time.time() < deadline:
            try:
                status = await client.get_order_status(symbol, order_id)
                if isinstance(status, dict):
                    state = str(status.get('status', status.get('state', status.get('orderStatus', '')))).lower()
                    if state in ('filled', 'closed', 'done', 'full_fill', 'completed'):
                        avg_price = float(status.get('avgPrice', status.get('avg_price',
                                         status.get('price', expected_price))))
                        filled_qty = float(status.get('filledQty', status.get('filled_qty',
                                          status.get('executedQty', status.get('dealSize', expected_qty)))))
                        if avg_price <= 0:
                            avg_price = expected_price
                        return {'filled': True, 'avg_price': avg_price, 'filled_qty': filled_qty}
                    elif state in ('cancelled', 'canceled', 'expired', 'rejected'):
                        logger.warning(f"⚠️  {side} order {order_id} was {state}")
                        return {'filled': False, 'avg_price': 0, 'filled_qty': 0}
                    # Still pending — wait and retry
            except Exception as e:
                logger.debug(f"Fill check error for {order_id}: {e}")
            
            await asyncio.sleep(self.FILL_POLL_INTERVAL)
        
        logger.warning(f"⏰ {side} order {order_id} fill timeout after {self.FILL_TIMEOUT_SEC}s")
        return {'filled': False, 'avg_price': 0, 'filled_qty': 0}
    
    async def _safe_cancel(self, client, symbol: str, order_id: str, side: str):
        """Try to cancel an unfilled order."""
        try:
            if hasattr(client, 'cancel_order'):
                await client.cancel_order(symbol, order_id)
                logger.info(f"✅ Cancelled {side} order {order_id}")
        except Exception as e:
            logger.warning(f"⚠️  Cancel {side} order {order_id} failed: {e}")
    
    async def _sync_balances_after_trade(self, buy_client, sell_client, buy_ex: str, sell_ex: str):
        """Force immediate balance sync after trade to get accurate balances."""
        await asyncio.sleep(1.0)  # Brief delay for exchange to process
        try:
            if self.balance_manager:
                for name, client in [(buy_ex, buy_client), (sell_ex, sell_client)]:
                    bal = await self.balance_manager._fetch_balance(name, client)
                    if bal:
                        logger.debug(f"📊 Post-trade balance sync: {name} OK")
        except Exception as e:
            logger.debug(f"Post-trade balance sync error: {e}")
    
    async def _emergency_close(self, exchange: str, symbol: str, side: str, qty: float, price: float, client):
        """
        Emergency close position when one leg of arbitrage fails.
        Places immediate market order in opposite direction.
        """
        try:
            logger.warning(f"🚨 EMERGENCY CLOSE: {side} {qty} {symbol} on {exchange}")
            result = await client.place_order(symbol, side, 'market', qty, price)
            logger.info(f"✅ Emergency close successful: {result}")
            return result
        except Exception as e:
            logger.error(f"❌ EMERGENCY CLOSE FAILED: {e}")
            # This is critical - manual intervention may be needed
            logger.error(f"🚨🚨🚨 MANUAL INTERVENTION REQUIRED: {side} {qty} {symbol} on {exchange}")
            return None
    
    def get_statistics(self) -> Dict:
        """Get execution statistics."""
        total_orders = len(self.order_history)
        total_profit = sum(o.get('net_profit', 0) for o in self.order_history)
        
        if total_orders == 0:
            return {
                'total_orders': 0,
                'total_profit': 0.0,
                'average_roi': 0.0,
                'mode': 'dry_run' if self.dry_run else 'live'
            }
        
        avg_roi = sum(o.get('roi_pct', 0) for o in self.order_history) / total_orders
        
        return {
            'total_orders': total_orders,
            'total_profit': total_profit,
            'average_roi': avg_roi,
            'mode': 'dry_run' if self.dry_run else 'live',
            'symbols_traded': list(set(o['symbol'] for o in self.order_history)),
        }
    
    def print_statistics(self):
        """Print execution statistics to console."""
        stats = self.get_statistics()
        mode_str = "🔵 DRY RUN" if self.dry_run else "🔴 LIVE"
        
        print(f"\n{'='*60}")
        print(f"  Order Executor Statistics ({mode_str})")
        print(f"{'='*60}")
        print(f"  Total Orders: {stats['total_orders']}")
        print(f"  Total Profit: ${stats['total_profit']:.4f} USDT")
        print(f"  Average ROI: {stats['average_roi']:.3f}%")
        if stats.get('symbols_traded'):
            print(f"  Symbols Traded: {', '.join(stats['symbols_traded'])}")
        print(f"{'='*60}\n")
