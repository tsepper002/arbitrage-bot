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
                 ml_spread_predictor = None,
                 order_flow_tracker = None,
                 iceberg_detector = None,
                 slippage_predictor = None,
                 nn_predictor = None,
                 rl_agent = None,
                 volatility_forecaster = None,
                 auto_parameter_tuner = None,
                 pattern_recognition = None,
                 market_adaptive_strategy = None,
                 ml_model_trainer = None,
                 twap_engine = None,
                 signal_allocator = None,
                 state_manager = None):
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
        self.order_flow_tracker = order_flow_tracker
        self.iceberg_detector = iceberg_detector
        self.slippage_predictor = slippage_predictor
        self.nn_predictor = nn_predictor
        self.rl_agent = rl_agent
        self.volatility_forecaster = volatility_forecaster
        self.auto_parameter_tuner = auto_parameter_tuner
        self.pattern_recognition = pattern_recognition
        self.market_adaptive_strategy = market_adaptive_strategy
        self.ml_model_trainer = ml_model_trainer
        self.twap_engine = twap_engine
        self.signal_allocator = signal_allocator
        self.state_manager = state_manager

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
        self._symbol_prices = {}  # Per-symbol price history for pattern recognition
        
        logger.info(f"ArbitrageEngine initialized: min_roi={self.min_net_pct}%, max_exposure=${self.max_exposure_usdt}, safety_factor={self.safety_factor}")

    def _fee_rate(self, exchange: str, side: str = "taker") -> float:
        p = self.params.get(exchange, {})
        if side == "maker":
            return p.get("maker", 0.0)
        return p.get("taker", 0.002)

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

        # Target exposure: use max_exposure_usdt to determine trade size
        if buy_price and buy_price > 0:
            target_qty = self.max_exposure_usdt / buy_price
        else:
            target_qty = self.default_qty  # fallback

        # final qty: min of target and liquidity (don't exceed what's available)
        if allowed_by_liquidity > 0:
            qty = min(target_qty, allowed_by_liquidity)
        else:
            qty = target_qty

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

        # --- PER-SYMBOL ML OBSERVATION (runs every scan, regardless of spreads) ---
        # Compute representative mid-price from first exchange with valid data
        _mid_price = 0.0
        _cached_regime = None  # Cache regime for use in pair loop
        for _ex in exchanges:
            _d = exmap.get(_ex, {})
            _b = _d.get("bid", 0) or 0
            _a = _d.get("ask", 0) or 0
            if _b > 0 and _a > 0:
                _mid_price = (_b + _a) / 2
                break

        if _mid_price > 0:
            # Volatility Forecaster — observe every symbol every scan
            if getattr(self, 'volatility_forecaster', None):
                try:
                    self.volatility_forecaster.observe(symbol, _mid_price)
                except Exception:
                    pass
            # Market Regime Detector — observe and cache regime for pair loop
            if self.market_regime_detector:
                try:
                    _cached_regime = self.market_regime_detector.detect(symbol, _mid_price)
                except Exception:
                    pass
            # Price history for pattern recognition / market adaptive
            hist = self._symbol_prices.setdefault(symbol, [])
            hist.append(_mid_price)
            if len(hist) > 200:
                self._symbol_prices[symbol] = hist[-200:]

        # ML Spread Predictor — compute best spread for this symbol and observe
        _best_cross_spread = 0.0
        if self.ml_spread_predictor and len(exchanges) >= 2:
            try:
                best_ask = float('inf')
                best_bid = 0.0
                for _ex in exchanges:
                    _d = exmap.get(_ex, {})
                    _a = _d.get("ask", 0) or 0
                    _b = _d.get("bid", 0) or 0
                    if _a > 0 and _a < best_ask:
                        best_ask = _a
                    if _b > best_bid:
                        best_bid = _b
                if best_ask < float('inf') and best_bid > 0 and best_ask > 0:
                    _best_cross_spread = (best_bid - best_ask) / best_ask
                    self.ml_spread_predictor.observe(symbol, _best_cross_spread)
            except Exception:
                pass

        # Neural Network — run predict on every symbol to populate cache (for dashboard)
        if getattr(self, 'nn_predictor', None) and _mid_price > 0:
            try:
                features = [_best_cross_spread * 100, 0.0, 0.0, _mid_price / 100000.0, 0.0]
                self.nn_predictor.predict(features, symbol)
            except Exception:
                pass

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
                        # observe() moved to per-symbol level above
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.debug(f"ML spread predictor error: {e}")
                
                # P5: Market Regime Detection — adjust min ROI based on cached regime
                regime_min_roi = self.min_net_pct
                if _cached_regime:
                    if _cached_regime == 'VOLATILE':
                        regime_min_roi = self.min_net_pct * 1.5
                    elif _cached_regime == 'CALM':
                        regime_min_roi = self.min_net_pct * 0.8
                
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

                # --- PRE-TRADE ML/EXECUTION CHECKS ---

                # M1: Order Flow Tracker — reduce confidence if smart money disagrees
                ml_skip = False
                if getattr(self, 'order_flow_tracker', None):
                    try:
                        smart_signal = self.order_flow_tracker.get_smart_money_signal(buy_ex, symbol)
                        if smart_signal == 'sell':
                            roi_pct *= 0.7  # Reduce confidence when smart money sells
                            logger.debug(f"Order flow: smart money SELL signal for {symbol}, reduced ROI to {roi_pct:.3f}%")
                    except Exception as e:
                        logger.debug(f"Order flow tracker error: {e}")

                # M2: Iceberg Detector — log hidden orders
                if getattr(self, 'iceberg_detector', None):
                    try:
                        orderbook_data = {'bids': bids[:10], 'asks': asks[:10]}
                        icebergs = self.iceberg_detector.detect(symbol, orderbook_data)
                        if icebergs:
                            logger.info(f"🧊 Iceberg orders detected for {symbol}: {len(icebergs)} hidden orders")
                    except Exception as e:
                        logger.debug(f"Iceberg detector error: {e}")

                # M3: Slippage Predictor — subtract predicted slippage from ROI
                predicted_slippage = 0.0
                if getattr(self, 'slippage_predictor', None):
                    try:
                        predicted_slippage = self.slippage_predictor.predict(
                            symbol, buy_ex, order_size_usdt=invested
                        )
                        roi_pct -= predicted_slippage * 100.0
                        logger.debug(f"Slippage prediction for {symbol}: {predicted_slippage*100:.4f}%, adjusted ROI: {roi_pct:.3f}%")
                    except Exception as e:
                        logger.debug(f"Slippage predictor error: {e}")

                # M4: Neural Network — skip if prediction confidence is very low
                nn_prob = None
                if getattr(self, 'nn_predictor', None):
                    try:
                        features = [roi_pct, gross_spread_pct, filled, invested, imbalance_adj]
                        nn_prob = self.nn_predictor.predict(features, symbol)
                        if nn_prob < 0.3:
                            ml_skip = True
                            logger.debug(f"NN predictor: low probability {nn_prob:.2f} for {symbol}, skipping")
                    except Exception as e:
                        logger.debug(f"Neural network predictor error: {e}")

                # M5: RL Agent — skip if action is SKIP
                rl_action = None
                if getattr(self, 'rl_agent', None) and not ml_skip:
                    try:
                        state_features = {
                            'spread': gross_spread_pct,
                            'volatility': 0.0,
                            'trend': imbalance_adj,
                        }
                        rl_action = self.rl_agent.get_action(state_features)
                        if rl_action == 'SKIP':
                            ml_skip = True
                            logger.debug(f"RL agent: SKIP action for {symbol}")
                    except Exception as e:
                        logger.debug(f"RL agent error: {e}")

                # M6: Volatility Forecaster + price history — moved to per-symbol level (before pair loop)

                # M7: Pattern Recognition — check for technical signals
                if getattr(self, 'pattern_recognition', None):
                    try:
                        price_hist = getattr(self, '_symbol_prices', {}).get(symbol, [])
                        if len(price_hist) >= 20:
                            signals = self.pattern_recognition.get_trading_signals(price_hist)
                            if signals.get('action') == 'SELL':
                                logger.debug(f"Pattern recognition: SELL signal for {symbol}, cautious")
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.debug(f"Pattern recognition error: {e}")

                # M8: Market Adaptive Strategy — adjust based on market regime
                if getattr(self, 'market_adaptive_strategy', None):
                    try:
                        price_hist = getattr(self, '_symbol_prices', {}).get(symbol, [])
                        if len(price_hist) >= 20:
                            regime = self.market_adaptive_strategy.detect_market_regime(price_hist)
                            params = self.market_adaptive_strategy.adapt_parameters(regime)
                            if params.get('confidence', 1.0) < 0.3:
                                logger.debug(f"Market adaptive: low confidence regime={regime}")
                    except (AttributeError, ValueError, TypeError) as e:
                        logger.debug(f"Market adaptive error: {e}")

                if ml_skip:
                    continue

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
                    # Feed near-misses as CROSS_EXCHANGE signals for visibility
                    nm = self._near_miss_count
                    if nm > 0:
                        self.strategy_dispatcher.record_engine_near_misses(nm)
                        self._near_miss_count = 0  # Reset after feeding
                for o in opps:
                    # Check risk manager before executing
                    if self.risk_manager:
                        can_trade, reason = self.risk_manager.check_can_trade(o)
                        if not can_trade:
                            logger.debug(f"Risk manager blocked trade: {reason}")
                            continue
                    
                    # Execute or log the opportunity
                    # For large orders, use TWAP to split into smaller slices
                    order_value = o.get('qty', 0) * o.get('buy_avg', 0)
                    twap_threshold = 20.0 if not settings.DRY_RUN else 50.0
                    if getattr(self, 'twap_engine', None) and order_value > twap_threshold:
                        try:
                            logger.info(f"📐 Large order ${order_value:.2f} > ${twap_threshold}, using TWAP execution")
                            await self.twap_engine.execute(
                                o['buy_ex'], o['symbol'], 'buy',
                                total_quantity=o['qty'], duration_seconds=30
                            )
                        except Exception as e:
                            logger.debug(f"TWAP execution error: {e}")
                    result = await self.executor.execute_arbitrage(o)
                    
                    # Record MISSED opportunity if blocked due to insufficient inventory
                    if result.get('status') == 'blocked' and self.signal_allocator:
                        missed_symbol = result.get('missed_symbol', o.get('symbol', ''))
                        missed_exchange = result.get('missed_exchange', '')
                        missed_side = result.get('missed_side', 'sell')
                        self.signal_allocator.record_miss(missed_symbol, missed_exchange, missed_side)
                        continue
                    
                    # Record trade to strategy manager AND dispatcher stats
                    if result.get('trade_info'):
                        # Feed trade count to strategy dispatcher for dashboard Trds column
                        if self.strategy_dispatcher and result['status'] in ('success', 'simulated'):
                            self.strategy_dispatcher.record_engine_trade('CROSS_EXCHANGE', symbol=o.get('symbol', ''))
                        
                        if self.strategy_manager:
                            strategy = o.get('strategy', 'cross_exchange')
                            # Both 'simulated' (dry-run) and 'success' (live) count as successful trades
                            success = result['status'] in ('success', 'simulated')
                            profit = result['trade_info'].get('net_profit', 0)
                            execution_time = result.get('execution_time', 0)
                            self.strategy_manager.record_trade(
                                strategy_name=strategy,
                                success=success,
                                profit=profit,
                                execution_time=execution_time
                            )
                        
                        # Record to signal allocator for inventory management
                        if self.signal_allocator and result['status'] in ('success', 'simulated'):
                            self.signal_allocator.record_trade(
                                symbol=o.get('symbol', ''),
                                strategy='CROSS_EXCHANGE',
                                exchange=o.get('buy_ex', ''),
                                roi_pct=o.get('roi_pct', 0)
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
                            if result['status'] in ('success', 'simulated'):
                                self.metrics_collector.record('successful_trades', 1)
                        
                        # --- POST-TRADE ML UPDATES ---
                        trade_profit = trade_info.get('net_profit', 0)
                        trade_successful = result['status'] in ('success', 'simulated')
                        
                        # MT1: Order Flow Tracker — track executed order
                        if getattr(self, 'order_flow_tracker', None):
                            try:
                                self.order_flow_tracker.track_order(
                                    o['buy_ex'], o['symbol'],
                                    {'amount': o['qty'], 'price': o['buy_avg'],
                                     'side': 'buy', 'timestamp': __import__('datetime').datetime.now()}
                                )
                            except Exception as e:
                                logger.debug(f"Order flow tracker post-trade error: {e}")
                        
                        # MT2: Slippage Predictor — observe actual vs predicted
                        if getattr(self, 'slippage_predictor', None):
                            try:
                                actual_slippage = abs(trade_info.get('slippage', 0.0))
                                self.slippage_predictor.observe(
                                    o['symbol'], o['buy_ex'],
                                    predicted_slippage=0.001, actual_slippage=actual_slippage,
                                    order_size=o.get('qty', 0) * o.get('buy_avg', 0)
                                )
                            except Exception as e:
                                logger.debug(f"Slippage predictor post-trade error: {e}")
                        
                        # MT3: RL Agent — update with trade outcome
                        if getattr(self, 'rl_agent', None):
                            try:
                                state = {'spread': o.get('roi_pct', 0), 'volatility': 0, 'trend': 0}
                                reward = trade_profit if trade_successful else -abs(trade_profit)
                                self.rl_agent.update(state, 'TRADE', reward, state)
                            except Exception as e:
                                logger.debug(f"RL agent post-trade error: {e}")
                        
                        # MT4: Neural Network — train on trade outcome
                        if getattr(self, 'nn_predictor', None):
                            try:
                                features = [o.get('roi_pct', 0), 0, o.get('qty', 0),
                                            o.get('qty', 0) * o.get('buy_avg', 0), 0]
                                target = 1.0 if trade_successful and trade_profit > 0 else 0.0
                                self.nn_predictor.train(features, target)
                            except Exception as e:
                                logger.debug(f"Neural network post-trade error: {e}")
                        
                        # MT5: ML Spread Predictor — observe actual spread
                        if getattr(self, 'ml_spread_predictor', None):
                            try:
                                actual_spread = o.get('roi_pct', 0) / 100.0
                                self.ml_spread_predictor.observe(o['symbol'], actual_spread)
                            except Exception as e:
                                logger.debug(f"ML spread predictor post-trade error: {e}")

                        # MT6: Auto Parameter Tuner — record performance
                        if getattr(self, 'auto_parameter_tuner', None):
                            try:
                                params = {'min_roi': self.min_net_pct, 'max_exposure': self.max_exposure_usdt}
                                profit = result.get('trade_info', {}).get('net_profit', 0)
                                self.auto_parameter_tuner.record_performance(params, profit, 1)
                            except (AttributeError, ValueError, TypeError) as e:
                                logger.debug(f"Auto param tuner post-trade error: {e}")

                        # MT7: ML Model Trainer — collect training data
                        if getattr(self, 'ml_model_trainer', None):
                            try:
                                profit = result.get('trade_info', {}).get('net_profit', 0)
                                self.ml_model_trainer.record_trade_data({
                                    'symbol': o['symbol'], 'roi': o['roi_pct'],
                                    'spread': o.get('gross', 0), 'profitable': profit > 0
                                })
                            except (AttributeError, ValueError, TypeError) as e:
                                logger.debug(f"ML model trainer post-trade error: {e}")
                    
                    # Update risk manager after trade
                    if self.risk_manager and result.get('trade_info'):
                        self.risk_manager.record_trade(result['trade_info'])
                    
                    # Record to state manager (trade journal + per-symbol P&L)
                    if result.get('status') in ('simulated', 'success') and result.get('trade_info'):
                        ti = result['trade_info']
                        ti['strategy'] = 'CROSS_EXCHANGE'
                        if hasattr(self, 'state_manager') and self.state_manager:
                            self.state_manager.record_trade_detail(ti)
                            self.state_manager.add_to_daily_pnl(ti.get('net', ti.get('net_profit', 0)))
                            self.state_manager.increment_trades()
                    
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