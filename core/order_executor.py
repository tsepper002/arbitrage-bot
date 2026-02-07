#!/usr/bin/env python3
"""
Order execution layer with dry_run and live modes.
Provides a safe interface for order placement with detailed logging.
"""
import time
import logging
from typing import Dict, Optional, List
from datetime import datetime
import settings

logger = logging.getLogger("order_executor")


class OrderExecutor:
    """
    Handles order execution with two modes:
    - dry_run (default): Simulates orders, logs actions without sending to exchanges
    - live: Placeholder for real order placement (requires authenticated API clients)
    """
    
    def __init__(self, dry_run: Optional[bool] = None):
        """
        Initialize order executor.
        
        Args:
            dry_run: If True, simulate orders. If None, uses settings.DRY_RUN
        """
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        self.order_history: List[Dict] = []
        self.trade_count_per_minute: Dict[int, int] = {}  # minute timestamp -> count
        self.last_trade_time_per_symbol: Dict[str, float] = {}  # symbol -> last trade timestamp
        
        if self.dry_run:
            logger.info("🔵 OrderExecutor initialized in DRY RUN mode (safe simulation)")
        else:
            logger.warning("🔴 OrderExecutor initialized in LIVE mode - REAL ORDERS WILL BE PLACED!")
    
    def can_trade(self, symbol: str) -> tuple[bool, Optional[str]]:
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
        }
        
        self._record_trade(symbol, order_info)
        
        return {
            'status': 'simulated',
            'order_info': order_info,
            'message': 'Orders simulated successfully (dry run mode)'
        }
    
    def _execute_live(self, opp: Dict) -> Dict:
        """
        Placeholder for live order execution.
        
        IMPORTANT: This requires:
        1. Authenticated API clients for each exchange
        2. Account balances and verification
        3. Proper error handling and order tracking
        4. Risk management checks
        
        Current implementation returns error - implement when infrastructure is ready.
        """
        symbol = opp['symbol']
        buy_ex = opp['buy_ex']
        sell_ex = opp['sell_ex']
        
        logger.error(
            f"🔴 LIVE ORDER EXECUTION NOT IMPLEMENTED\n"
            f"   Attempted to execute: {symbol} on {buy_ex} -> {sell_ex}\n"
            f"   This requires authenticated exchange clients and should be implemented carefully.\n"
            f"   Set DRY_RUN=True in settings.py to use simulation mode."
        )
        
        return {
            'status': 'error',
            'reason': 'Live trading not implemented - requires authenticated exchange clients',
            'opportunity': opp,
            'message': 'Enable DRY_RUN mode or implement authenticated trading infrastructure'
        }
        
        # TEMPLATE for future implementation:
        # try:
        #     # 1. Verify sufficient balances
        #     # buy_balance = await self.get_balance(buy_ex, quote_currency)
        #     # sell_balance = await self.get_balance(sell_ex, base_currency)
        #     
        #     # 2. Place buy order
        #     # buy_order = await self.place_order(buy_ex, symbol, 'buy', qty, buy_price)
        #     
        #     # 3. Wait for buy fill confirmation
        #     # await self.wait_for_fill(buy_order)
        #     
        #     # 4. Place sell order
        #     # sell_order = await self.place_order(sell_ex, symbol, 'sell', qty, sell_price)
        #     
        #     # 5. Wait for sell fill confirmation
        #     # await self.wait_for_fill(sell_order)
        #     
        #     # 6. Record successful trade
        #     # self._record_trade(symbol, order_details)
        #     
        #     # return {'status': 'success', 'order_info': order_details}
        # except Exception as e:
        #     # Handle errors, possibly cancel unfilled orders
        #     # logger.exception(f"Live order execution failed: {e}")
        #     # return {'status': 'error', 'reason': str(e)}
    
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
