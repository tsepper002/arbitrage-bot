# Updated arbitrage engine: auto qty selection from topK liquidity, safety factor, exposure cap reads from config.
import asyncio
import csv
import os
import time
import logging
from typing import List, Tuple, Optional, Dict, Set
from datetime import datetime
from .exchange_config import EXCHANGE_PARAMS
from . import trader_config
from .order_executor import OrderExecutor
import settings

logger = logging.getLogger("arbitrage_engine")

def simulate_execution_from_book(levels: List[Tuple[float, float]], qty: float) -> Tuple[float, float]:
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
    avg = cost / filled
    return avg, filled

class ArbitrageEngine:
    def __init__(self, store, *,
                 default_qty: Optional[float] = None,
                 min_net_pct: Optional[float] = None,
                 persist_path: Optional[str] = None,
                 max_exposure_usdt: Optional[float] = None,
                 safety_factor: Optional[float] = None,
                 topk: Optional[int] = None,
                 executor: Optional[OrderExecutor] = None,
                 risk_manager = None,
                 strategy_manager = None,
                 strategy_dispatcher = None,
                 flash_crash_protector = None,
                 wash_trading_filter = None,
                 orderbook_imbalance_detector = None,
                 trade_journal = None,
                 profit_attribution = None,
                 metrics_collector = None,
                 market_regime_detector = None,
                 fee_optimizer = None,
                 ml_spread_predictor = None):
        self.store = store
        self.params = EXCHANGE_PARAMS
        
        # Use settings.py values as defaults
        self.default_qty = default_qty if default_qty is not None else settings.DEFAULT_QUANTITY
        self.min_net_pct = min_net_pct if min_net_pct is not None else settings.MIN_NET_ROI_PCT
        self.persist_path = persist_path if persist_path is not None else settings.OPPORTUNITIES_CSV_PATH
        self.safety_factor = safety_factor if safety_factor is not None else settings.SAFETY_FACTOR
        self.topk = topk if topk is not None else settings.ORDERBOOK_TOP_K

        # max exposure: use settings or compute from trader_config
        if max_exposure_usdt is not None:
            self.max_exposure_usdt = max_exposure_usdt
        elif settings.MAX_EXPOSURE_USDT:
            self.max_exposure_usdt = settings.MAX_EXPOSURE_USDT
        else:
            sc_usdt = trader_config.get_starting_capital_usdt(None)
            if sc_usdt:
                # Conservative: use 50% of starting capital as per-trade max exposure
                self.max_exposure_usdt = max(sc_usdt * 0.5, 50.0)
            else:
                self.max_exposure_usdt = 200.0

        # Initialize order executor (use provided or create new)
        self.executor = executor if executor is not None else OrderExecutor()
        
        # Optional integrations
        self.risk_manager = risk_manager
        self.strategy_manager = strategy_manager
        self.strategy_dispatcher = strategy_dispatcher
        
        # Professional components
        self.flash_crash_protector = flash_crash_protector
        self.wash_trading_filter = wash_trading_filter
        self.orderbook_imbalance_detector = orderbook_imbalance_detector
        self.trade_journal = trade_journal
        self.profit_attribution = profit_attribution
        self.metrics_collector = metrics_collector
        
        # ML modules
        self.market_regime_detector = market_regime_detector
        self.fee_optimizer = fee_optimizer
        self.ml_spread_predictor = ml_spread_predictor

        # Event-driven scanning state
        self.updated_symbols: Set[str] = set()
        self.last_scan_time: Dict[str, float] = {}
        
        # Spread analytics — track best spread seen each cycle
        self._best_spread_pct = 0.0
        self._best_spread_info = ""
        self._near_miss_count = 0
        self._total_pairs_analyzed = 0

        # ensure persistence file
        if not os.path.exists(self.persist_path):
            with open(self.persist_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["ts", "symbol", "buy_ex", "sell_ex", "qty", "buy_price", "sell_price", "net", "roi_pct"])

        self.recent_cache = {}
        
        logger.info(f"ArbitrageEngine initialized: min_roi={self.min_net_pct}%, max_exposure=${self.max_exposure_usdt}, safety_factor={self.safety_factor}")

    def _fee_rate(self, exchange: str, side: str = "taker") -> float:
        p = self.params.get(exchange, {})
        if side == "maker":
            return p.get("maker", 0.0)
        return p.get("taker", p.get("taker", 0.002))

    def _persist_opportunity(self, info: Dict):
        try:
            with open(self.persist_path, "a", newline="") as f:
                w = csv.writer(f)
                w.writerow([time.time(), info["symbol"], info["buy_ex"], info["sell_ex"],
                            info["qty"], info["buy_avg"], info["sell_avg"], info["net"], info["roi_pct"]])
        except Exception:
            pass

    def _choose_qty(self, buy_levels, sell_levels, buy_price) -> float:
        """
        Choose qty based on available liquidity across topK levels, safety factor and exposure cap.
        buy_levels: asks ascending list [(price,size),...]
        sell_levels: bids descending list [(price,size),...]
        buy_price: current buy price (best ask)
        """
        # total available at topK (base asset)
        avail_buy = sum(s for p, s in buy_levels[:self.topk]) if buy_levels else 0.0
        avail_sell = sum(s for p, s in sell_levels[:self.topk]) if sell_levels else 0.0
        total_avail = min(avail_buy, avail_sell)

        # limit by safety factor
        allowed_by_liquidity = total_avail * self.safety_factor

        # limit by exposure in USDT
        if buy_price and buy_price > 0:
            allowed_by_exposure = self.max_exposure_usdt / buy_price
        else:
            allowed_by_exposure = self.default_qty  # fallback

        # final qty
        qty = min(self.default_qty, allowed_by_liquidity if allowed_by_liquidity > 0 else self.default_qty, allowed_by_exposure)
        # enforce small positive
        return max(qty, 0.0)

    async def scan_once(self, symbol: str, prefunded: bool = True) -> List[Dict]:
        # Cleanup old entries from recent_cache to prevent memory leak
        now = time.time()
        cutoff = now - 60.0  # Remove entries older than 60 seconds
        keys_to_remove = [k for k, ts in self.recent_cache.items() if ts < cutoff]
        for k in keys_to_remove:
            del self.recent_cache[k]
        if keys_to_remove:
            logger.debug(f"Cleaned {len(keys_to_remove)} old entries from recent_cache")
        
        snap = self.store.snapshot()
        exmap = snap.get(symbol, {})
        exchanges = list(exmap.keys())
        res = []
        if len(exchanges) < 2:
            return res

        # BIDIRECTIONAL SCAN FIX: Check ALL directed pairs (A->B AND B->A)
        # Previous version only checked exchanges[i+1:] which missed 50% of opportunities
        for i, buy_ex in enumerate(exchanges):
            # Check this exchange as buy against ALL other exchanges as sell
            for j, sell_ex in enumerate(exchanges):
                if i == j:  # Skip same exchange
                    continue
                    
                buy = exmap.get(buy_ex, {})
                sell = exmap.get(sell_ex, {})

                asks = buy.get("asks_levels")
                bids = sell.get("bids_levels")

                if not asks:
                    a = buy.get("ask")
                    a_size = buy.get("ask_size") or 0.0
                    asks = [(a, a_size)] if a is not None else []
                if not bids:
                    b = sell.get("bid")
                    b_size = sell.get("bid_size") or 0.0
                    bids = [(b, b_size)] if b is not None else []

                if not asks or not bids:
                    continue

                # S1 PREFILTER: Quick top-of-book spread check before expensive simulation
                # Skip if gross spread is too small to be profitable after fees
                top_bid = bids[0][0]
                top_ask = asks[0][0]
                gross_spread_pct = ((top_bid - top_ask) / top_ask) * 100.0 if top_ask > 0 else 0
                
                buy_fee = self._fee_rate(buy_ex, "taker")
                sell_fee = self._fee_rate(sell_ex, "taker")
                sum_fees_pct = (buy_fee + sell_fee) * 100.0
                
                self._total_pairs_analyzed += 1
                
                # Track best spread for dashboard transparency
                if gross_spread_pct > self._best_spread_pct:
                    self._best_spread_pct = gross_spread_pct
                    self._best_spread_info = f"{symbol} {buy_ex}→{sell_ex}"
                    self._best_spread_fees_pct = sum_fees_pct
                
                # Prefilter: skip if spread < 80% of fees (won't be profitable)
                if gross_spread_pct < sum_fees_pct * 0.8:
                    # Near-miss: spread is >30% of fee threshold (engine is working)
                    if gross_spread_pct > sum_fees_pct * 0.3:
                        self._near_miss_count += 1
                    continue

                # choose qty adaptively
                buy_price_est = asks[0][0] if asks else None
                qty = self._choose_qty(asks, bids, buy_price_est)
                if qty <= 0:
                    continue

                # A5 RISK CHECK: Skip anomalous spreads (likely data errors)
                if gross_spread_pct > settings.ANOMALOUS_SPREAD_PCT:
                    logger.warning(f"Skipping anomalous spread {gross_spread_pct:.2f}% for {symbol} {buy_ex}->{sell_ex} (threshold: {settings.ANOMALOUS_SPREAD_PCT}%)")
                    continue

                buy_avg, buy_filled = simulate_execution_from_book(asks, qty)
                sell_avg, sell_filled = simulate_execution_from_book(bids, qty)
                filled = min(buy_filled, sell_filled)
                if filled <= 0:
                    continue

                buy_fee = self._fee_rate(buy_ex, "taker")
                sell_fee = self._fee_rate(sell_ex, "taker")
                fees = (buy_avg * filled) * buy_fee + (sell_avg * filled) * sell_fee

                gross = (sell_avg - buy_avg) * filled
                net = gross - fees

                invested = buy_avg * filled
                roi_pct = (net / invested) * 100 if invested else 0.0
                
                # PROFESSIONAL RISK CHECKS
                # P1: Flash Crash Protection - Check if market is safe to trade
                if self.flash_crash_protector:
                    if self.flash_crash_protector.should_stop_trading(symbol):
                        logger.warning(f"⚠️ Flash crash protection activated for {symbol}, skipping trade")
                        if self.metrics_collector:
                            self.metrics_collector.record('flash_crash_blocks', 1)
                        continue
                
                # P2: Wash Trading Filter — skip if volume looks suspicious
                if self.wash_trading_filter:
                    try:
                        is_suspicious, suspicion_score = self.wash_trading_filter.is_suspicious_trade(
                            symbol, buy_avg, filled
                        )
                        if is_suspicious:
                            logger.warning(f"⚠️ Wash trading detected for {symbol} (score={suspicion_score:.2f}), skipping")
                            if self.metrics_collector:
                                self.metrics_collector.record('wash_trade_blocks', 1)
                            continue
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.debug(f"Wash trading filter error: {e}")
                
                # P3: Orderbook Imbalance — adjust confidence based on order flow
                # Positive imbalance_adj means BUY pressure confirms our trade → lower ROI bar
                imbalance_adj = 0.0
                if self.orderbook_imbalance_detector and asks and bids:
                    try:
                        from professional_features.orderbook_imbalance_detector import OrderBookSnapshot
                        snapshot = OrderBookSnapshot(
                            timestamp=datetime.now(),
                            bids=bids[:10],
                            asks=asks[:10],
                            exchange=buy_ex,
                            symbol=symbol
                        )
                        signal = self.orderbook_imbalance_detector.analyze_orderbook(snapshot)
                        # Positive adj = favorable (lowers required ROI)
                        # Negative adj = unfavorable (raises required ROI)
                        if signal.signal in ('BUY', 'STRONG_BUY') and signal.confidence > 0.5:
                            imbalance_adj = signal.confidence * 0.01  # Up to +1% favorable
                        elif signal.signal in ('SELL', 'STRONG_SELL') and signal.confidence > 0.7:
                            imbalance_adj = -0.01  # Unfavorable
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.debug(f"Orderbook imbalance error: {e}")
                
                # P4: ML Spread Predictor — observe and predict spread behavior
                if self.ml_spread_predictor:
                    try:
                        # Cross-exchange spread: positive = profitable
                        cross_spread_pct = gross_spread_pct / 100.0
                        predicted_spread = self.ml_spread_predictor.predict(symbol, {
                            'current_spread': cross_spread_pct,
                            'roi_pct': roi_pct,
                            'buy_ex': buy_ex,
                            'sell_ex': sell_ex
                        })
                        # Update predictor with observed spread
                        self.ml_spread_predictor.update(symbol, cross_spread_pct)
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.debug(f"ML spread predictor error: {e}")
                
                # P5: Market Regime Detection — adjust min ROI based on market conditions
                regime_min_roi = self.min_net_pct
                if self.market_regime_detector:
                    try:
                        mid_price = (top_bid + top_ask) / 2 if (top_bid and top_ask) else 0
                        if mid_price > 0:
                            regime = self.market_regime_detector.detect(symbol, mid_price)
                            if regime == 'VOLATILE':
                                # In volatile markets, opportunities are wider but riskier
                                regime_min_roi = self.min_net_pct * 1.5
                            elif regime == 'CALM':
                                # In calm markets, accept smaller spreads
                                regime_min_roi = self.min_net_pct * 0.8
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.debug(f"Market regime detection error: {e}")
                
                # P6: Fee Optimizer — record trade fee for VIP tier analysis
                if self.fee_optimizer:
                    try:
                        self.fee_optimizer.record_trade_fee(
                            buy_ex, symbol, invested, fees, 'taker'
                        )
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.debug(f"Fee optimizer error: {e}")
                
                # P7: Record metrics for monitoring
                if self.metrics_collector:
                    self.metrics_collector.record('opportunities_found', 1)
                    self.metrics_collector.record('roi_pct', roi_pct)
                    self.metrics_collector.record('net_profit_usdt', net)

                info = {
                    "symbol": symbol,
                    "buy_ex": buy_ex,
                    "sell_ex": sell_ex,
                    "qty": filled,
                    "buy_avg": buy_avg,
                    "sell_avg": sell_avg,
                    "gross": gross,
                    "fees": fees,
                    "net": net,
                    "roi_pct": roi_pct,
                }

                if net > 0 and roi_pct >= (regime_min_roi - imbalance_adj):
                    # dedupe and persist
                    key = f"{symbol}:{buy_ex}->{sell_ex}:{round(buy_avg,6)}:{round(sell_avg,6)}"
                    now = time.time()
                    last_ts = self.recent_cache.get(key, 0)
                    if now - last_ts > 5.0:
                        self.recent_cache[key] = now
                        self._persist_opportunity(info)
                        res.append(info)
                        
                        # USER-FRIENDLY INFO LOGGING
                        logger.info(f"💰 OPPORTUNITY: {symbol} | Buy {buy_ex} @ {buy_avg:.6f} → Sell {sell_ex} @ {sell_avg:.6f} | ROI: {roi_pct:.3f}% | Net: ${net:.2f}")
                elif roi_pct > 0:
                    # Log near-miss opportunities occasionally (for debugging)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Near-miss: {symbol} {buy_ex}->{sell_ex} ROI={roi_pct:.3f}% (need {self.min_net_pct}%)")
        
        # Sort by net profit
        res.sort(key=lambda x: x["net"], reverse=True)
        
        # Limit to max concurrent opportunities
        if len(res) > settings.MAX_CONCURRENT_OPPORTUNITIES:
            logger.debug(f"Limiting to top {settings.MAX_CONCURRENT_OPPORTUNITIES} opportunities (found {len(res)})")
            res = res[:settings.MAX_CONCURRENT_OPPORTUNITIES]
        
        return res

    def mark_symbol_updated(self, symbol: str):
        """Mark a symbol as having updated data (for event-driven scanning)."""
        if settings.EVENT_DRIVEN_SCAN:
            self.updated_symbols.add(symbol)

    async def run(self, symbols: List[str]):
        """Main scanning loop with event-driven optimization."""
        logger.info(f"🚀 Starting arbitrage engine for {len(symbols)} symbols: {', '.join(symbols)}")
        logger.info(f"⚙️ Settings: MIN_ROI={self.min_net_pct}%, MAX_EXPOSURE=${self.max_exposure_usdt}, SCAN_INTERVAL={settings.SCAN_INTERVAL_SEC}s")
        logger.info(f"📊 Waiting for price data from exchanges...")
        last_stats_print = time.time()
        
        while True:
            scan_start = time.time()
            
            # Determine which symbols to scan
            if settings.EVENT_DRIVEN_SCAN and self.updated_symbols:
                # Only scan symbols that have been updated
                symbols_to_scan = list(self.updated_symbols)
                self.updated_symbols.clear()
            else:
                # Scan all symbols
                symbols_to_scan = symbols
            
            # SPEED: Take snapshot ONCE per cycle (not per symbol)
            snap = self.store.snapshot()
            
            # Filter to symbols that pass throttle check
            ready_symbols = []
            for s in symbols_to_scan:
                last_scan = self.last_scan_time.get(s, 0)
                if scan_start - last_scan >= settings.MIN_SCAN_INTERVAL_PER_SYMBOL_SEC:
                    self.last_scan_time[s] = scan_start
                    ready_symbols.append(s)
            
            # SPEED: Scan all symbols concurrently instead of sequentially.
            # Previous: for s in symbols: await scan_once(s)  →  O(N × latency)
            # Now: asyncio.gather(*[scan_once(s)])  →  O(1 × latency) for CPU-bound work
            if ready_symbols:
                scan_results = await asyncio.gather(
                    *(self.scan_once(s) for s in ready_symbols),
                    return_exceptions=True
                )
            else:
                scan_results = []
            
            for s, opps in zip(ready_symbols, scan_results):
                # Log exceptions from individual scans at ERROR level (not DEBUG)
                # A KeyError/AttributeError here means a component is crashing silently
                if isinstance(opps, Exception):
                    logger.error(f"❌ Scan error for {s}: {type(opps).__name__}: {opps}")
                    continue
                if not opps:
                    continue

                # Feed opportunity count back to strategy dispatcher
                if self.strategy_dispatcher:
                    self.strategy_dispatcher.record_engine_opportunities(len(opps))
                for o in opps:
                    # Check risk manager before executing
                    if self.risk_manager:
                        can_trade, reason = self.risk_manager.check_can_trade(o)
                        if not can_trade:
                            logger.debug(f"Risk manager blocked trade: {reason}")
                            continue
                    
                    # Execute or log the opportunity
                    result = await self.executor.execute_arbitrage(o)
                    
                    # Record trade to strategy manager
                    if self.strategy_manager and result.get('trade_info'):
                        strategy = o.get('strategy', 'cross_exchange')
                        success = result['status'] == 'success'
                        profit = result['trade_info'].get('net_profit', 0)
                        execution_time = result.get('execution_time', 0)
                        self.strategy_manager.record_trade(
                            strategy_name=strategy,
                            success=success,
                            profit=profit,
                            execution_time=execution_time
                        )
                    
                    # PROFESSIONAL ANALYTICS: Record trade details
                    if result.get('trade_info'):
                        trade_info = result['trade_info']
                        
                        # Record to Trade Journal
                        if self.trade_journal:
                            self.trade_journal.record_trade({
                                'symbol': o['symbol'],
                                'side': 'buy_sell',  # arbitrage
                                'amount': o['qty'],
                                'price': o['buy_avg'],
                                'fee': trade_info.get('total_fees', 0),
                                'profit': trade_info.get('net_profit', 0),
                                'strategy': o.get('strategy', 'cross_exchange'),
                                'exchange': f"{o['buy_ex']}/{o['sell_ex']}",
                                'notes': f"ROI: {o.get('roi_pct', 0):.3f}%"
                            })
                        
                        # Record to Profit Attribution
                        if self.profit_attribution:
                            self.profit_attribution.add_trade({
                                'strategy': o.get('strategy', 'cross_exchange'),
                                'exchange': o['buy_ex'],
                                'symbol': o['symbol'],
                                'profit': trade_info.get('net_profit', 0)
                            })
                        
                        # Record metrics
                        if self.metrics_collector:
                            self.metrics_collector.record('trades_executed', 1)
                            self.metrics_collector.record('execution_time_ms', result.get('execution_time', 0) * 1000)
                            if result['status'] == 'success':
                                self.metrics_collector.record('successful_trades', 1)
                    
                    # Update risk manager after trade
                    if self.risk_manager and result.get('trade_info'):
                        self.risk_manager.record_trade(result['trade_info'])
                    
                    if result['status'] == 'simulated':
                        # Already logged by executor
                        pass
                    elif result['status'] == 'success':
                        logger.info(f"✅ Trade executed successfully: {result.get('summary', '')}")
                    elif result['status'] == 'blocked':
                        logger.debug(f"Trade blocked: {result['reason']}")
                    elif result['status'] == 'error':
                        logger.error(f"Execution error: {result.get('reason', 'Unknown')}")
            
            # Print statistics periodically (reuse snap from above)
            if time.time() - last_stats_print > 60.0:
                # Print executor statistics
                self.executor.print_statistics()
                
                # Print scanning status
                active_symbols = len([s for s in symbols if s in snap and snap[s]])
                total_exchanges = sum(len(snap.get(s, {})) for s in symbols) if snap else 0
                logger.info(f"📊 STATUS: Scanning {active_symbols}/{len(symbols)} symbols across {total_exchanges} exchange connections")
                
                # Show which exchanges have data
                if snap:
                    exchanges_with_data = set()
                    for s in symbols:
                        if s in snap:
                            exchanges_with_data.update(snap[s].keys())
                    if exchanges_with_data:
                        logger.info(f"📡 Active exchanges: {', '.join(sorted(exchanges_with_data))}")
                    else:
                        logger.warning("⚠️ No exchange data available in price store")
                
                last_stats_print = time.time()
            
            # Sleep based on configured interval
            await asyncio.sleep(settings.SCAN_INTERVAL_SEC)