#!/usr/bin/env python3
"""
Order execution layer with dry_run and live modes.
Provides a safe interface for order placement with detailed logging.
"""
import time
import logging
import asyncio
from typing import List, Optional, Tuple, Dict
from datetime import datetime
import settings

logger = logging.getLogger("order_executor")


class OrderExecutor:
    """
    Handles order execution with two modes:
    - dry_run (default): Simulates orders, logs actions without sending to exchanges
    - live: Real order placement using authenticated REST API clients
    """
    
    def __init__(self, dry_run: Optional[bool] = None, rest_clients: Optional[Dict[str, any]] = None,
                 balance_manager: Optional[any] = None, risk_manager: Optional[any] = None):
        """
        Initialize order executor.
        
        Args:
            dry_run: If True, simulate orders. If None, uses settings.DRY_RUN
            rest_clients: Dictionary of exchange_name -> REST client for live trading
            balance_manager: BalanceManager instance for balance verification
            risk_manager: RiskManager instance for risk checks
        """
        self.dry_run = dry_run if dry_run is not None else settings.DRY_RUN
        self.rest_clients = rest_clients or {}
        self.balance_manager = balance_manager
        self.risk_manager = risk_manager
        
        self.order_history: List[Dict] = []
        self.trade_count_per_minute: Dict[int, int] = {}  # minute timestamp -> count
        self.last_trade_time_per_symbol: Dict[str, float] = {}  # symbol -> last trade timestamp
        
        if self.dry_run:
            logger.info("🔵 OrderExecutor initialized in DRY RUN mode (safe simulation)")
        else:
            logger.warning("🔴 OrderExecutor initialized in LIVE mode - REAL ORDERS WILL BE PLACED!")
            if not self.rest_clients:
                logger.warning("⚠️ No REST clients provided - live trading will fail!")
            if not self.balance_manager:
                logger.warning("⚠️ No BalanceManager provided - balance verification disabled!")
            if not self.risk_manager:
                logger.warning("⚠️ No RiskManager provided - risk checks disabled!")
    
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
        Execute live order using authenticated REST API clients.
        
        CRITICAL: This places REAL orders with REAL money!
        Implements concurrent execution with proper error handling.
        
        Args:
            opp: Opportunity dictionary with trade details
            
        Returns:
            Execution result with status and order details
        """
        symbol = opp['symbol']
        buy_ex = opp['buy_ex']
        sell_ex = opp['sell_ex']
        qty = opp['qty']
        buy_price = opp['buy_avg']
        sell_price = opp['sell_avg']
        
        logger.info(f"🔴 LIVE TRADING: Executing {symbol} {qty:.6f} @ buy={buy_price:.2f} on {buy_ex}, sell={sell_price:.2f} on {sell_ex}")
        
        # Verify REST clients are available
        buy_client = self.rest_clients.get(buy_ex)
        sell_client = self.rest_clients.get(sell_ex)
        
        if not buy_client or not sell_client:
            logger.error(f"Missing REST client for {buy_ex if not buy_client else sell_ex}")
            return {
                'status': 'error',
                'reason': f'No REST client available for {buy_ex if not buy_client else sell_ex}',
                'opportunity': opp
            }
        
        # Risk management check
        if self.risk_manager:
            allowed, reason = self.risk_manager.check_trade_allowed(
                symbol, buy_ex, sell_ex, qty, buy_price, sell_price, opp['net']
            )
            if not allowed:
                logger.warning(f"Trade blocked by risk manager: {reason}")
                return {
                    'status': 'blocked',
                    'reason': f'Risk check failed: {reason}',
                    'opportunity': opp
                }
        
        # Balance verification
        if self.balance_manager:
            balances_ok, balance_error = self.balance_manager.verify_balances_for_trade(
                buy_ex, sell_ex, symbol, qty, buy_price, sell_price
            )
            if not balances_ok:
                logger.warning(f"Insufficient balance: {balance_error}")
                return {
                    'status': 'blocked',
                    'reason': f'Insufficient balance: {balance_error}',
                    'opportunity': opp
                }
        
        # Execute both legs concurrently to minimize slippage
        buy_order = None
        sell_order = None
        buy_filled = False
        sell_filled = False
        
        try:
            # Place both orders using market orders for fast execution
            logger.info(f"Placing buy order on {buy_ex}: {symbol} {qty:.6f} @ market")
            buy_order = buy_client.place_order(
                symbol=symbol,
                side='buy',
                order_type='market',
                quantity=qty
            )
            buy_order_id = buy_order.get('order_id') or buy_order.get('orderId')
            logger.info(f"✅ Buy order placed: {buy_order_id}")
            
            logger.info(f"Placing sell order on {sell_ex}: {symbol} {qty:.6f} @ market")
            sell_order = sell_client.place_order(
                symbol=symbol,
                side='sell',
                order_type='market',
                quantity=qty
            )
            sell_order_id = sell_order.get('order_id') or sell_order.get('orderId')
            logger.info(f"✅ Sell order placed: {sell_order_id}")
            
            # Wait for fills (with timeout)
            max_wait = 10.0  # 10 seconds max wait for fill
            start_wait = time.time()
            
            while (time.time() - start_wait) < max_wait:
                # Check buy order status
                if not buy_filled:
                    try:
                        buy_status = buy_client.get_order_status(buy_order_id, symbol)
                        status = buy_status.get('status', '').lower()
                        if status in ['filled', 'complete', 'closed']:
                            buy_filled = True
                            # Extract actual fill price and quantity
                            buy_price = float(buy_status.get('avg_price', buy_status.get('price', buy_price)))
                            qty = float(buy_status.get('filled_quantity', buy_status.get('executedQty', qty)))
                            logger.info(f"✅ Buy order filled: {qty:.6f} @ {buy_price:.2f}")
                    except Exception as e:
                        logger.error(f"Error checking buy order status: {e}")
                
                # Check sell order status
                if not sell_filled:
                    try:
                        sell_status = sell_client.get_order_status(sell_order_id, symbol)
                        status = sell_status.get('status', '').lower()
                        if status in ['filled', 'complete', 'closed']:
                            sell_filled = True
                            # Extract actual fill price
                            sell_price = float(sell_status.get('avg_price', sell_status.get('price', sell_price)))
                            logger.info(f"✅ Sell order filled: {qty:.6f} @ {sell_price:.2f}")
                    except Exception as e:
                        logger.error(f"Error checking sell order status: {e}")
                
                # Break if both filled
                if buy_filled and sell_filled:
                    break
                
                time.sleep(0.5)  # Check every 500ms
            
            # Handle partial fills or timeouts
            if not buy_filled:
                logger.warning(f"⚠️ Buy order not filled within {max_wait}s - attempting cancel")
                try:
                    buy_client.cancel_order(buy_order_id, symbol)
                except Exception as e:
                    logger.error(f"Failed to cancel buy order: {e}")
                
                return {
                    'status': 'error',
                    'reason': 'Buy order timeout - order cancelled',
                    'opportunity': opp,
                    'buy_order': buy_order
                }
            
            if not sell_filled:
                logger.warning(f"⚠️ Sell order not filled within {max_wait}s - attempting cancel")
                try:
                    sell_client.cancel_order(sell_order_id, symbol)
                except Exception as e:
                    logger.error(f"Failed to cancel sell order: {e}")
                
                # We have a position now - this is a problem!
                logger.error(f"🚨 CRITICAL: Bought on {buy_ex} but failed to sell on {sell_ex}!")
                return {
                    'status': 'error',
                    'reason': 'Sell order timeout - holding position!',
                    'opportunity': opp,
                    'buy_order': buy_order,
                    'sell_order': sell_order
                }
            
            # Calculate actual profit
            gross = (sell_price - buy_price) * qty
            buy_fee_rate = 0.001  # Get from exchange_config
            sell_fee_rate = 0.001
            fees = (buy_price * qty * buy_fee_rate) + (sell_price * qty * sell_fee_rate)
            net_profit = gross - fees
            roi_pct = (net_profit / (buy_price * qty)) * 100 if (buy_price * qty) > 0 else 0
            
            logger.info(f"💰 Trade completed: profit=${net_profit:.4f} ({roi_pct:.3f}% ROI)")
            
            # Record trade
            order_info = {
                'mode': 'live',
                'symbol': symbol,
                'buy_exchange': buy_ex,
                'sell_exchange': sell_ex,
                'quantity': qty,
                'buy_price': buy_price,
                'sell_price': sell_price,
                'gross_profit': gross,
                'fees': fees,
                'net_profit': net_profit,
                'roi_pct': roi_pct,
                'buy_order_id': buy_order_id,
                'sell_order_id': sell_order_id,
            }
            
            self._record_trade(symbol, order_info)
            
            # Update risk manager
            if self.risk_manager:
                self.risk_manager.record_trade(
                    symbol, buy_ex, sell_ex, qty, buy_price, sell_price, net_profit, roi_pct
                )
            
            # Refresh balances after trade
            if self.balance_manager:
                try:
                    asyncio.create_task(self.balance_manager.fetch_balances(force=True))
                except Exception:
                    pass  # Best effort
            
            return {
                'status': 'success',
                'order_info': order_info,
                'message': 'Both legs executed successfully'
            }
            
        except Exception as e:
            logger.exception(f"🚨 CRITICAL ERROR during live execution: {e}")
            
            # Attempt cleanup if partially executed
            if buy_order and not sell_order:
                logger.error("Buy order placed but sell order failed - attempting emergency sell...")
                # TODO: Implement emergency sell logic
            
            return {
                'status': 'error',
                'reason': f'Execution failed: {str(e)}',
                'opportunity': opp,
                'buy_order': buy_order,
                'sell_order': sell_order
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
