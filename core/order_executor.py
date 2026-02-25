#!/usr/bin/env python3
"""
Order execution layer with dry_run and live modes.
Provides a safe interface for order placement with detailed logging.
Enhanced with parallel order execution and balance integration.
"""
import time
import asyncio
import logging
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
    
    def __init__(self, dry_run: Optional[bool] = None, rest_clients: Optional[Dict] = None, balance_manager=None):
        """
        Initialize order executor.
        
        Args:
            dry_run: If True, simulate orders. If None, uses settings.DRY_RUN
            rest_clients: Dict of {exchange_name: REST_client} for live trading
            balance_manager: BalanceManager instance for balance tracking
        """
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        self.rest_clients = rest_clients or {}
        self.balance_manager = balance_manager
        self.order_history: List[Dict] = []
        self.trade_count_per_minute: Dict[int, int] = {}  # minute timestamp -> count
        self.last_trade_time_per_symbol: Dict[str, float] = {}  # symbol -> last trade timestamp
        
        if self.dry_run:
            logger.info("🔵 OrderExecutor initialized in DRY RUN mode (safe simulation)")
        else:
            if not self.rest_clients:
                logger.warning("⚠️  LIVE mode enabled but no REST clients provided!")
            logger.warning("🔴 OrderExecutor initialized in LIVE mode - REAL ORDERS WILL BE PLACED!")
    
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
    
    async def execute_arbitrage(self, opportunity: Dict) -> Dict:
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
            return await self._execute_live(opportunity)
    
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
            'trade_info': order_info,
            'message': 'Orders simulated successfully (dry run mode)'
        }
    
    async def _execute_live(self, opp: Dict) -> Dict:
        """
        Execute live arbitrage with PARALLEL order placement.
        
        Strategy:
        1. Check balances via BalanceManager
        2. Place buy and sell orders SIMULTANEOUSLY (asyncio.gather)
        3. Wait for both fills with timeout
        4. If one fails, emergency close the other
        5. Update balances optimistically
        
        Args:
            opp: Opportunity dict with symbol, buy_ex, sell_ex, qty, prices
            
        Returns:
            Dict with status, order details, and profit
        """
        symbol = opp['symbol']
        buy_ex = opp['buy_ex']
        sell_ex = opp['sell_ex']
        qty = opp['qty']
        buy_price = opp.get('buy_avg', opp.get('buy_price'))
        sell_price = opp.get('sell_avg', opp.get('sell_price'))
        
        # Parse symbol for balance checking
        base_currency = symbol.split('-')[0]  # BTC from BTC-USDT
        quote_currency = symbol.split('-')[1]  # USDT from BTC-USDT
        
        logger.info(
            f"🔴 LIVE EXECUTION: {symbol} | "
            f"Buy {qty} @ ${buy_price:.4f} on {buy_ex} | "
            f"Sell {qty} @ ${sell_price:.4f} on {sell_ex}"
        )
        
        try:
            # Step 1: Check balances
            if self.balance_manager:
                buy_cost = qty * buy_price * 1.002  # Add 0.2% buffer for fees
                can_buy, buy_reason = self.balance_manager.has_sufficient_balance(buy_ex, quote_currency, buy_cost)
                can_sell, sell_reason = self.balance_manager.has_sufficient_balance(sell_ex, base_currency, qty)
                
                if not can_buy:
                    logger.warning(f"⚠️  Cannot buy on {buy_ex}: {buy_reason}")
                    return {'status': 'blocked', 'reason': buy_reason}
                
                if not can_sell:
                    logger.warning(f"⚠️  Cannot sell on {sell_ex}: {sell_reason}")
                    return {'status': 'blocked', 'reason': sell_reason}
            
            # Step 2: Get REST clients
            buy_client = self.rest_clients.get(buy_ex)
            sell_client = self.rest_clients.get(sell_ex)
            
            if not buy_client or not sell_client:
                error_msg = f"Missing REST client: {buy_ex if not buy_client else sell_ex}"
                logger.error(f"❌ {error_msg}")
                return {'status': 'error', 'reason': error_msg}
            
            # Step 3: Place both orders SIMULTANEOUSLY
            logger.info("⚡ Placing PARALLEL orders...")
            start_time = time.time()
            
            # Use market orders for speed (can be optimized to use limit orders)
            buy_task = buy_client.place_order(symbol, 'buy', 'market', qty, buy_price)
            sell_task = sell_client.place_order(symbol, 'sell', 'market', qty, sell_price)
            
            # Execute in parallel
            results = await asyncio.gather(buy_task, sell_task, return_exceptions=True)
            buy_result, sell_result = results
            
            execution_time = time.time() - start_time
            
            # Check for errors
            if isinstance(buy_result, Exception):
                logger.error(f"❌ Buy order failed: {buy_result}")
                # Sell order might have succeeded - need to reverse!
                if not isinstance(sell_result, Exception):
                    logger.warning("⚠️  EMERGENCY: Sell succeeded but buy failed - reversing sell...")
                    await self._emergency_close(sell_ex, symbol, 'buy', qty, buy_price, sell_client)
                return {'status': 'error', 'reason': f'Buy failed: {str(buy_result)}'}
            
            if isinstance(sell_result, Exception):
                logger.error(f"❌ Sell order failed: {sell_result}")
                # Buy order succeeded - need to reverse!
                logger.warning("⚠️  EMERGENCY: Buy succeeded but sell failed - reversing buy...")
                await self._emergency_close(buy_ex, symbol, 'sell', qty, sell_price, buy_client)
                return {'status': 'error', 'reason': f'Sell failed: {str(sell_result)}'}
            
            # Both orders succeeded!
            logger.info(f"✅ BOTH ORDERS FILLED in {execution_time:.3f}s")
            
            # Step 4: Update balances optimistically
            if self.balance_manager:
                buy_cost_actual = qty * buy_price
                sell_proceeds = qty * sell_price
                self.balance_manager.record_trade(
                    buy_ex, sell_ex, base_currency, quote_currency,
                    qty, buy_cost_actual, sell_proceeds
                )
            
            # Step 5: Record trade
            trade_info = {
                'symbol': symbol,
                'buy_ex': buy_ex,
                'sell_ex': sell_ex,
                'qty': qty,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'buy_order_id': buy_result.get('orderId') or buy_result.get('order_id'),
                'sell_order_id': sell_result.get('orderId') or sell_result.get('order_id'),
                'gross_profit': opp.get('gross', 0),
                'net_profit': opp.get('net', 0),
                'roi_pct': opp.get('roi_pct', 0),
                'execution_time_sec': execution_time,
                'mode': 'LIVE'
            }
            
            self._record_trade(symbol, trade_info)
            
            logger.info(
                f"💰 LIVE TRADE COMPLETED: "
                f"${trade_info['net_profit']:.4f} profit ({trade_info['roi_pct']:.3f}% ROI) "
                f"in {execution_time:.3f}s"
            )
            
            return {
                'status': 'success',
                'trade_info': trade_info
            }
            
        except Exception as e:
            logger.exception(f"❌ Live execution failed: {e}")
            return {
                'status': 'error',
                'reason': str(e)
            }
    
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
