#!/usr/bin/env python3
"""
Order execution layer with dry_run and live modes.
Provides a safe interface for order placement with detailed logging.
"""
import asyncio
import time
import logging
import os
from typing import List, Optional, Tuple, Dict
from datetime import datetime
import settings
from utils.telegram import TelegramNotifier

logger = logging.getLogger("order_executor")


class OrderExecutor:
    """
    Handles order execution with two modes:
    - dry_run (default): Simulates orders, logs actions without sending to exchanges
    - live: Places real orders via authenticated REST API clients
    """
    
    def __init__(self, dry_run: Optional[bool] = None, rest_clients: Optional[Dict] = None):
        """
        Initialize order executor.
        
        Args:
            dry_run: If True, simulate orders. If None, uses settings.DRY_RUN
            rest_clients: Dict of exchange_name -> REST client instance (for live trading)
        """
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        self.order_history: List[Dict] = []
        self.trade_count_per_minute: Dict[int, int] = {}  # minute timestamp -> count
        self.last_trade_time_per_symbol: Dict[str, float] = {}  # symbol -> last trade timestamp
        
        # Virtual capital tracking for dry run
        self.virtual_balance_usdt = settings.VIRTUAL_CAPITAL_USDT if self.dry_run else 0.0
        self.initial_virtual_balance = self.virtual_balance_usdt
        
        # REST clients for live trading (exchange_name -> client)
        self.rest_clients: Dict = rest_clients or {}
        
        self.telegram = TelegramNotifier()

        if self.dry_run:
            logger.info("🔵 OrderExecutor initialized in DRY RUN mode (safe simulation)")
        else:
            configured = list(self.rest_clients.keys()) if self.rest_clients else []
            logger.warning(f"🔴 OrderExecutor initialized in LIVE mode — exchanges: {configured or 'NONE'}")
    
    def can_trade(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """
        Check if trading is allowed based on rate limits and cooldowns.
        
        Returns:
            (can_trade, reason) tuple
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
    
    def execute_arbitrage(self, opportunity: Dict) -> Dict:
        """
        Execute an arbitrage opportunity.
        
        Args:
            opportunity: Dict with keys:
                - symbol: trading pair (e.g., "BTC-USDT")
                - buy_ex: exchange to buy from
                - sell_ex: exchange to sell to
                - qty: quantity to trade
                - buy_avg: average buy price
                - sell_avg: average sell price
                - net: expected net profit (USDT)
                - roi_pct: return on investment percentage
        
        Returns:
            Execution result dict with status and details
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
        
        if self.dry_run:
            return self._execute_dry_run(opportunity)
        else:
            return self._execute_live(opportunity)
    
    def _execute_dry_run(self, opp: Dict) -> Dict:
        """Simulate order execution with detailed logging."""
        symbol = opp['symbol']
        buy_ex = opp['buy_ex']
        sell_ex = opp['sell_ex']
        qty = opp['qty']
        buy_price = opp['buy_avg']
        sell_price = opp['sell_avg']
        net_profit = opp['net']
        roi_pct = opp['roi_pct']
        
        # Check virtual capital
        trade_cost = qty * buy_price
        if trade_cost > self.virtual_balance_usdt:
            logger.info(f"⚠️ [DRY RUN] Insufficient virtual capital: need ${trade_cost:.2f}, have ${self.virtual_balance_usdt:.2f}")
            return {
                'status': 'blocked',
                'reason': f'Insufficient virtual capital: ${self.virtual_balance_usdt:.2f} < ${trade_cost:.2f}',
                'opportunity': opp
            }
        
        logger.info(
            f"💰 [DRY RUN] ARBITRAGE OPPORTUNITY DETECTED\n"
            f"   Symbol: {symbol}\n"
            f"   Buy:  {qty:.6f} @ ${buy_price:.6f} on {buy_ex} (cost: ${qty * buy_price:.2f})\n"
            f"   Sell: {qty:.6f} @ ${sell_price:.6f} on {sell_ex} (receive: ${qty * sell_price:.2f})\n"
            f"   Net Profit: ${net_profit:.4f} ({roi_pct:.3f}% ROI)"
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
            'virtual_balance': self.virtual_balance_usdt,
        }
        
        self._record_trade(symbol, order_info)

        # Send Telegram notification (fire and forget)
        try:
            asyncio.ensure_future(self.telegram.notify_opportunity(opp))
        except RuntimeError:
            # No running event loop (e.g. called from sync test context)
            pass

        # Update virtual balance: subtract buy cost, add sell proceeds
        self.virtual_balance_usdt = self.virtual_balance_usdt - trade_cost + (qty * sell_price)
        order_info['virtual_balance'] = self.virtual_balance_usdt
        logger.info(f"💼 [DRY RUN] Virtual Balance: ${self.virtual_balance_usdt:.2f} USDT")
        
        return {
            'status': 'simulated',
            'order_info': order_info,
            'message': 'Orders simulated successfully (dry run mode)'
        }
    
    def _execute_live(self, opp: Dict) -> Dict:
        """
        Execute a real trade via authenticated REST API clients.

        Flow:
        1. Verify REST clients are available for both exchanges
        2. Place buy order on the cheaper exchange
        3. Place sell order on the more expensive exchange
        4. Record the trade and send Telegram notification
        """
        symbol = opp['symbol']
        buy_ex = opp['buy_ex']
        sell_ex = opp['sell_ex']
        qty = opp['qty']
        buy_price = opp['buy_avg']
        sell_price = opp['sell_avg']
        net_profit = opp['net']
        roi_pct = opp['roi_pct']

        # Verify REST clients are available
        buy_client = self.rest_clients.get(buy_ex)
        sell_client = self.rest_clients.get(sell_ex)

        if not buy_client or not sell_client:
            missing = []
            if not buy_client:
                missing.append(buy_ex)
            if not sell_client:
                missing.append(sell_ex)
            logger.error(
                f"🔴 Cannot execute live trade: no REST client for {', '.join(missing)}\n"
                f"   Set DRY_RUN=True or configure API keys for these exchanges."
            )
            return {
                'status': 'error',
                'reason': f'No REST client configured for: {", ".join(missing)}',
                'opportunity': opp,
            }

        logger.info(
            f"🔴 [LIVE] EXECUTING ARBITRAGE TRADE\n"
            f"   Symbol: {symbol}\n"
            f"   Buy:  {qty:.6f} @ ${buy_price:.6f} on {buy_ex}\n"
            f"   Sell: {qty:.6f} @ ${sell_price:.6f} on {sell_ex}\n"
            f"   Expected Net: ${net_profit:.4f} ({roi_pct:.3f}% ROI)"
        )

        # Convert symbol format for exchange APIs (BTC-USDT -> BTCUSDT for most)
        api_symbol = symbol.replace("-", "")

        try:
            loop = asyncio.get_event_loop()

            # Place buy order
            buy_result = loop.run_until_complete(
                buy_client.place_order(api_symbol, qty, buy_price)
            )
            logger.info(f"🟢 [LIVE] Buy order placed on {buy_ex}: {buy_result}")

            # Place sell order
            sell_result = loop.run_until_complete(
                sell_client.place_order(api_symbol, qty, sell_price)
            )
            logger.info(f"🟢 [LIVE] Sell order placed on {sell_ex}: {sell_result}")

            # Record trade
            order_info = {
                'mode': 'live',
                'symbol': symbol,
                'buy_exchange': buy_ex,
                'sell_exchange': sell_ex,
                'quantity': qty,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'net_profit': net_profit,
                'roi_pct': roi_pct,
                'buy_order_result': buy_result,
                'sell_order_result': sell_result,
            }
            self._record_trade(symbol, order_info)

            # Send Telegram notification
            try:
                asyncio.ensure_future(self.telegram.notify_opportunity(opp))
            except RuntimeError:
                pass

            return {
                'status': 'executed',
                'order_info': order_info,
                'message': f'Live orders placed on {buy_ex} and {sell_ex}',
            }

        except Exception as e:
            logger.exception(f"🔴 [LIVE] Order execution failed: {e}")
            return {
                'status': 'error',
                'reason': str(e),
                'opportunity': opp,
            }
    
    def get_statistics(self) -> Dict:
        """Get execution statistics."""
        total_orders = len(self.order_history)
        total_profit = sum(o.get('net_profit', 0) for o in self.order_history)
        
        if total_orders == 0:
            return {
                'total_orders': 0,
                'total_profit': 0.0,
                'average_roi': 0.0,
                'mode': 'dry_run' if self.dry_run else 'live',
                'virtual_balance': self.virtual_balance_usdt,
                'virtual_pnl': self.virtual_balance_usdt - self.initial_virtual_balance,
            }
        
        avg_roi = sum(o.get('roi_pct', 0) for o in self.order_history) / total_orders
        
        return {
            'total_orders': total_orders,
            'total_profit': total_profit,
            'average_roi': avg_roi,
            'mode': 'dry_run' if self.dry_run else 'live',
            'symbols_traded': list(set(o['symbol'] for o in self.order_history)),
            'virtual_balance': self.virtual_balance_usdt,
            'virtual_pnl': self.virtual_balance_usdt - self.initial_virtual_balance,
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
        if self.dry_run:
            print(f"  Virtual Balance: ${self.virtual_balance_usdt:.2f} USDT")
            print(f"  Virtual P&L: ${self.virtual_balance_usdt - self.initial_virtual_balance:.2f} USDT")
        print(f"{'='*60}\n")
