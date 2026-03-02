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
    # Compound reinvestment: max growth factor for trade size
    COMPOUND_MAX_MULTIPLIER = 2.0
    # MEXC-first routing: prefer low-fee exchange if price within this % proximity
    LOW_FEE_PROXIMITY_PCT = 0.02
    # Profit reserve: 30% of profits are locked (untouchable), 70% reinvested
    PROFIT_REINVEST_PCT = 0.70
    PROFIT_RESERVE_PCT = 0.30
    
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
                 state_manager = None,
                 capital_manager = None,
                 semi_hft_engine = None):
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
        self.capital_manager = capital_manager
        self.semi_hft = semi_hft_engine  # Semi-HFT engine for professional execution

        # Event-driven scanning state
        self.updated_symbols: Set[str] = set()
        self.last_scan_time: Dict[str, float] = {}
        
        # Spread analytics — track best spread seen each cycle
        self._best_spread_pct = 0.0
        self._best_spread_info = ""
        self._best_spread_fees_pct = 0.0
        self._near_miss_count = 0
        self._total_pairs_analyzed = 0

        # ensure persistence file
        if not os.path.exists(self.persist_path):
            with open(self.persist_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["ts", "symbol", "buy_ex", "sell_ex", "qty", "buy_price", "sell_price", "net", "roi_pct"])

        self.recent_cache = {}
        self._symbol_prices = {}  # Per-symbol price history for pattern recognition
        self._jit_history = {}    # Track JIT ops: (exchange,symbol) → last_timestamp
        self._jit_total_cost = 0.0  # Total USDT spent on JIT fees
        
        # Compound reinvestment: profits grow trade size (capped at 2× base)
        self._total_profit = 0.0
        self._reinvested_profit = 0.0   # 70% of profits → grows trade size
        self._reserved_profit = 0.0     # 30% of profits → untouchable reserve
        self._base_exposure = self.max_exposure_usdt
        self._compound_max = self._base_exposure * self.COMPOUND_MAX_MULTIPLIER
        
        # MEXC-first routing: prefer MEXC as buy-side (0.05% taker vs 0.10%+ others)
        self._low_fee_exchanges = ['MEXC']  # Exchanges with lowest taker fees
        self._low_fee_proximity = self.LOW_FEE_PROXIMITY_PCT / 100.0

        # Spread persistence filter: only trade spreads that survive long enough
        self._spread_first_seen: Dict[str, float] = {}  # key -> first_seen_ms
        self.MIN_SPREAD_HOLD_MS = 500  # Spread must hold for 500ms before trading

        # Exchange latency tracking for execution feasibility checks
        self._exchange_latency_ms: Dict[str, float] = {}  # exchange -> avg round-trip ms
        self.MAX_COMBINED_LATENCY_MS = 1000  # Skip if combined latency > 1s
        self.DEFAULT_EXCHANGE_LATENCY_MS = 200  # Assumed latency when no data available
        self.LATENCY_EMA_ALPHA = 0.3  # Smoothing factor for latency EMA
        self.MAX_VWAP_SLIPPAGE_PCT = settings.MAX_VWAP_SLIPPAGE_PCT
        
        logger.info(f"ArbitrageEngine initialized: min_roi={self.min_net_pct}%, max_exposure=${self.max_exposure_usdt}, safety_factor={self.safety_factor}")

    @property
    def best_spread_pct(self) -> float:
        """Public access to best observed spread (for CapitalManager volatility proxy)."""
        return self._best_spread_pct

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

    # JIT acquisition constants
    JIT_FEE_SLIPPAGE_BUFFER = 1.003  # 0.3% buffer for fees + slippage on JIT buys
    JIT_USDT_SAFETY_MARGIN = 0.95    # Use 95% of USDT, keep 5% for fee rounding
    JIT_BALANCE_SYNC_DELAY = 0.5     # Seconds to wait for balance sync after live order
    JIT_COOLDOWN_SECONDS = 300       # 5 min cooldown per exchange per symbol
    JIT_MIN_PROFIT_RATIO = 3.0       # Arb profit must be ≥3× the JIT fee cost

    async def _jit_acquire(self, opportunity: Dict, blocked_result: Dict) -> bool:
        """
        Just-In-Time inventory acquisition with FEE PROTECTION:
        - Only executes if arb profit > JIT fee cost × 3
        - 5-minute cooldown per exchange/symbol to prevent fee spiral
        - Deducts exchange trading fees from virtual balances
        
        Returns True if acquisition succeeded and trade should be retried.
        """
        symbol = opportunity.get('symbol', '')
        missed_ex = blocked_result.get('missed_exchange', '')
        missed_side = blocked_result.get('missed_side', 'sell')
        
        if not symbol or not missed_ex:
            return False
        
        # SAFETY CHECK 1: Cooldown — max 1 JIT per exchange/symbol per 5 minutes
        jit_key = (missed_ex, symbol)
        now = time.time()
        last_jit = self._jit_history.get(jit_key, 0)
        if now - last_jit < self.JIT_COOLDOWN_SECONDS:
            return False  # Too recent, skip to prevent fee spiral
        
        # SAFETY CHECK 2: Profit must exceed JIT fee cost
        arb_net = opportunity.get('net', 0)
        arb_qty = opportunity.get('qty', 0)
        arb_price = opportunity.get('buy_avg', 0) or opportunity.get('sell_avg', 0)
        from core.exchange_config import EXCHANGE_PARAMS
        ex_fee = EXCHANGE_PARAMS.get(missed_ex, {}).get('taker', 0.001)
        jit_fee_cost = arb_qty * arb_price * ex_fee  # Fee for the JIT buy/sell
        
        if arb_net < jit_fee_cost * self.JIT_MIN_PROFIT_RATIO:
            # Arb profit doesn't justify the JIT fee cost
            logger.debug(
                f"JIT skipped {symbol} on {missed_ex}: arb profit ${arb_net:.4f} "
                f"< {self.JIT_MIN_PROFIT_RATIO}× JIT fee ${jit_fee_cost:.4f}"
            )
            return False
        
        base_currency = symbol.split('-')[0] if '-' in symbol else symbol.replace('USDT', '')
        bm = self.executor.balance_manager if self.executor else None
        if not bm:
            return False
        
        if missed_side == 'sell':
            # SELL-SIDE MISS: Need base coin on sell exchange → buy it with USDT
            acquisition_price = opportunity.get('sell_avg', 0)
            qty = opportunity.get('qty', 0)
            if acquisition_price <= 0 or qty <= 0:
                return False
            
            usdt_available = bm.get_balance(missed_ex, 'USDT')
            cost = qty * acquisition_price * self.JIT_FEE_SLIPPAGE_BUFFER
            
            if usdt_available < max(cost, 1.0):
                if usdt_available < 1.0:
                    return False
                qty = (usdt_available * self.JIT_USDT_SAFETY_MARGIN) / (acquisition_price * self.JIT_FEE_SLIPPAGE_BUFFER)
                cost = qty * acquisition_price * self.JIT_FEE_SLIPPAGE_BUFFER
            
            # Deduct exchange trading fee from received quantity
            qty_after_fee = qty * (1.0 - ex_fee)
            
            return await self._jit_execute_buy(
                missed_ex, symbol, base_currency, qty_after_fee, cost, opportunity
            )
        
        elif missed_side == 'buy':
            # BUY-SIDE MISS: Need USDT on buy exchange → sell any held base coin
            acquisition_price = opportunity.get('buy_avg', 0)
            qty = opportunity.get('qty', 0)
            if acquisition_price <= 0 or qty <= 0:
                return False
            
            # Check if we have ANY base coin on buy exchange we can sell to free USDT
            base_held = bm.get_balance(missed_ex, base_currency)
            if base_held > 0 and base_held * acquisition_price >= 1.0:
                # We already have some of this coin — sell it for USDT  
                sell_qty = min(base_held, qty)
                usdt_received = sell_qty * acquisition_price * (1.0 - ex_fee)
                
                return await self._jit_execute_sell(
                    missed_ex, symbol, base_currency, sell_qty, usdt_received, opportunity
                )
            
            # Try selling ANY other coin we have on this exchange
            if hasattr(bm, 'get_all_balances'):
                all_balances = bm.get_all_balances().get(missed_ex, {})
            else:
                all_balances = {}
            for coin, amount in all_balances.items():
                if coin == 'USDT' or amount <= 0:
                    continue
                coin_symbol = f"{coin}-USDT"
                coin_price = self._get_coin_price(coin_symbol, missed_ex)
                if coin_price <= 0 or amount * coin_price < 1.0:
                    continue
                # Sell this coin to free up USDT
                usdt_received = amount * coin_price * (1.0 - ex_fee)
                return await self._jit_execute_sell(
                    missed_ex, coin_symbol, coin, amount, usdt_received, opportunity
                )
            
            return False
        
        return False
    
    def _get_coin_price(self, symbol: str, exchange: str = None) -> float:
        """Get current price for a symbol from PriceStore, preferring specific exchange."""
        snap = self.store.snapshot()
        exmap = snap.get(symbol, {})
        # Try specific exchange first
        if exchange and exchange in exmap:
            bid = exmap[exchange].get('bid', 0) or 0
            if bid > 0:
                return bid
        # Fallback: any exchange with a valid price
        for ex in exmap.values():
            bid = ex.get('bid', 0) or 0
            if bid > 0:
                return bid
        return 0.0
    
    async def _jit_execute_buy(self, exchange, symbol, base_currency, qty, cost, opportunity) -> bool:
        """Execute JIT buy (USDT → base coin) on an exchange. Records cooldown to prevent fee spiral."""
        bm = self.executor.balance_manager
        
        if settings.DRY_RUN:
            bm.update_balance_optimistic(exchange, 'USDT', -cost)
            bm.update_balance_optimistic(exchange, base_currency, qty)
            opportunity['qty'] = qty
            opportunity['net'] = qty * (opportunity.get('sell_avg', 0) - opportunity.get('buy_avg', 0))
            # Record JIT operation for cooldown
            self._jit_history[(exchange, symbol)] = time.time()
            from core.exchange_config import EXCHANGE_PARAMS
            fee = EXCHANGE_PARAMS.get(exchange, {}).get('taker', 0.001)
            self._jit_total_cost += cost * fee
            logger.info(f"⚡ JIT BUY: {qty:.4f} {base_currency} on {exchange} (${cost:.2f}, fee=${cost*fee:.4f})")
            return True
        else:
            rest_clients = getattr(self.executor, 'rest_clients', getattr(self, '_rest_clients', None))
            if not rest_clients or exchange not in rest_clients:
                return False
            try:
                result = await rest_clients[exchange].place_order(
                    symbol=symbol.replace('-', ''), side='buy', order_type='market',
                    quantity=qty, price=None
                )
                if result:
                    self._jit_history[(exchange, symbol)] = time.time()
                    logger.info(f"⚡ JIT BUY: {qty:.4f} {base_currency} on {exchange} (${cost:.2f})")
                    opportunity['qty'] = qty
                    opportunity['net'] = qty * (opportunity.get('sell_avg', 0) - opportunity.get('buy_avg', 0))
                    await asyncio.sleep(self.JIT_BALANCE_SYNC_DELAY)
                    return True
            except Exception as e:
                logger.warning(f"JIT buy failed on {exchange}: {e}")
            return False
    
    async def _jit_execute_sell(self, exchange, symbol, base_currency, qty, usdt_received, opportunity) -> bool:
        """Execute JIT sell (base coin → USDT) on an exchange to free up capital."""
        bm = self.executor.balance_manager
        
        if settings.DRY_RUN:
            bm.update_balance_optimistic(exchange, base_currency, -qty)
            bm.update_balance_optimistic(exchange, 'USDT', usdt_received)
            self._jit_history[(exchange, symbol)] = time.time()
            logger.info(f"⚡ JIT SELL: {qty:.4f} {base_currency} → ${usdt_received:.2f} USDT on {exchange}")
            return True
        else:
            rest_clients = getattr(self.executor, 'rest_clients', getattr(self, '_rest_clients', None))
            if not rest_clients or exchange not in rest_clients:
                return False
            try:
                result = await rest_clients[exchange].place_order(
                    symbol=symbol.replace('-', ''), side='sell', order_type='market',
                    quantity=qty, price=None
                )
                if result:
                    self._jit_history[(exchange, symbol)] = time.time()
                    logger.info(f"⚡ JIT SELL: {qty:.4f} {base_currency} → ${usdt_received:.2f} USDT on {exchange}")
                    await asyncio.sleep(self.JIT_BALANCE_SYNC_DELAY)
                    return True
            except Exception as e:
                logger.warning(f"JIT sell failed on {exchange}: {e}")
            return False

    def _choose_qty(self, buy_levels, sell_levels, buy_price) -> float:
        """
        Choose qty based on available liquidity across topK levels, safety factor and exposure cap.
        Engine 2.0: Uses CapitalManager.compute_position_usdt() for adaptive sizing.
        """
        # total available at topK (base asset)
        avail_buy = sum(s for p, s in buy_levels[:self.topk]) if buy_levels else 0.0
        avail_sell = sum(s for p, s in sell_levels[:self.topk]) if sell_levels else 0.0
        total_avail = min(avail_buy, avail_sell)

        # limit by safety factor
        allowed_by_liquidity = total_avail * self.safety_factor

        # Engine 2.0: Use CapitalManager for adaptive position sizing
        if self.capital_manager and buy_price and buy_price > 0:
            # Depth in USDT at best levels (use large fallback when no liquidity data)
            UNLIMITED_DEPTH_USDT = 1e9
            depth_usdt = allowed_by_liquidity * buy_price if allowed_by_liquidity > 0 else UNLIMITED_DEPTH_USDT
            # Get adaptive position size from CapitalManager
            position_usdt = self.capital_manager.compute_position_usdt(
                exchange_balance_usdt=self.max_exposure_usdt,
                depth_best_usdt=depth_usdt,
                exposure_limit_usdt=self.max_exposure_usdt,
            )
            target_qty = position_usdt / buy_price if position_usdt > 0 else self.default_qty
        else:
            # Fallback: legacy compound logic
            compound_exposure = min(self._base_exposure + self._reinvested_profit, self._compound_max)
            effective_exposure = max(compound_exposure, self._base_exposure)
            if buy_price and buy_price > 0:
                target_qty = effective_exposure / buy_price
            else:
                target_qty = self.default_qty

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

        # Cleanup stale spread observations (>10 seconds old)
        spread_cutoff = now * 1000 - 10000
        stale_spreads = [k for k, ts in self._spread_first_seen.items() if ts < spread_cutoff]
        for k in stale_spreads:
            del self._spread_first_seen[k]
        
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

        # --- Engine 2.0: CapitalManager kill-logic checks ---
        cm = self.capital_manager
        if cm and not cm.is_coin_enabled(symbol):
            return res  # Coin disabled by kill-logic

        # SEMI-HFT: Pre-filter to TOP N exchanges by latency + stability.
        # This is the KEY optimization: instead of scanning 5×5=20 pairs,
        # we scan 3×3=6 pairs (or 2×2=4 at micro level), focusing on the
        # exchanges most likely to execute successfully.
        # Level mapping: coin_limit=1 → 2 exchanges, coin_limit=3 → 4, coin_limit=5 → 6
        MIN_EXCHANGES_FOR_ARB = 2
        hft = self.semi_hft
        if hft and settings.SEMI_HFT_ENABLED:
            max_exchanges = cm.level.coin_limit + 1 if cm else 3
            max_exchanges = max(max_exchanges, MIN_EXCHANGES_FOR_ARB)
            exchanges = hft.get_top_exchanges(exchanges, n=max_exchanges)
            if len(exchanges) < MIN_EXCHANGES_FOR_ARB:
                return res  # Not enough healthy exchanges

        # BIDIRECTIONAL SCAN FIX: Check ALL directed pairs (A->B AND B->A)
        # Previous version only checked exchanges[i+1:] which missed 50% of opportunities
        for i, buy_ex in enumerate(exchanges):
            # Engine 2.0: Skip disabled exchanges
            if cm and not cm.is_exchange_enabled(buy_ex):
                continue
            # Semi-HFT: Skip excluded exchanges (latency/error/kill-switch)
            hft = self.semi_hft
            if hft and hft.should_exclude_exchange(buy_ex):
                continue

            # Check this exchange as buy against ALL other exchanges as sell
            for j, sell_ex in enumerate(exchanges):
                if i == j:  # Skip same exchange
                    continue
                
                # Engine 2.0: Skip disabled exchanges
                if cm and not cm.is_exchange_enabled(sell_ex):
                    continue
                # Semi-HFT: Skip excluded exchanges
                if hft and hft.should_exclude_exchange(sell_ex):
                    continue
                    
                buy = exmap.get(buy_ex, {})
                sell = exmap.get(sell_ex, {})

                # §1.3 Orderbook staleness check: reject if data > 200ms old
                now_ts = time.time()
                max_age_sec = settings.MAX_ORDERBOOK_AGE_MS / 1000.0
                buy_ts = buy.get("ts", 0)
                sell_ts = sell.get("ts", 0)
                if buy_ts and (now_ts - buy_ts) > max_age_sec:
                    continue  # buy-side orderbook stale
                if sell_ts and (now_ts - sell_ts) > max_age_sec:
                    continue  # sell-side orderbook stale

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
                
                # §4 MAKER-FIRST FEE OPTIMIZATION:
                # Buy side uses maker fee (limit order), sell side uses taker fee (market order)
                # This is critical for MEXC where maker=0% vs taker=0.05%
                buy_fee = self._fee_rate(buy_ex, "maker" if settings.MAKER_FIRST_ENABLED else "taker")
                sell_fee = self._fee_rate(sell_ex, "taker")
                sum_fees_pct = (buy_fee + sell_fee) * 100.0
                
                self._total_pairs_analyzed += 1
                
                # Track best spread for dashboard transparency
                if gross_spread_pct > self._best_spread_pct:
                    self._best_spread_pct = gross_spread_pct
                    self._best_spread_info = f"{symbol} {buy_ex}→{sell_ex}"
                    self._best_spread_fees_pct = sum_fees_pct
                
                # Engine 2.0: Dynamic threshold replaces static fee prefilter
                # threshold = fees + level cushion + latency_risk + volatility_buffer
                # Semi-HFT: Enhanced with p95 slippage + execution failure rate + vol regime
                if hft and settings.SEMI_HFT_ENABLED:
                    dynamic_min_spread = hft.dynamic_threshold_v2(
                        sum_fees_pct, buy_ex, sell_ex, cm
                    )
                    # Feed volatility data
                    hft.update_volatility(gross_spread_pct)
                    # HTX filter: higher latency → only use for wide spreads
                    if ('HTX' in (buy_ex, sell_ex)) and cm and not cm.should_use_htx(gross_spread_pct):
                        continue
                elif cm:
                    avg_latency = (
                        self._exchange_latency_ms.get(buy_ex, self.DEFAULT_EXCHANGE_LATENCY_MS) +
                        self._exchange_latency_ms.get(sell_ex, self.DEFAULT_EXCHANGE_LATENCY_MS)
                    ) / 2.0
                    dynamic_min_spread = cm.dynamic_threshold(sum_fees_pct, avg_latency)
                    
                    # HTX filter: higher latency → only use for wide spreads
                    if ('HTX' in (buy_ex, sell_ex)) and not cm.should_use_htx(gross_spread_pct):
                        continue
                else:
                    dynamic_min_spread = sum_fees_pct * 0.8  # fallback: static 80% of fees
                
                # SIGNAL COLLECTION: Record signals BEFORE threshold gate
                # This is critical: coin selection needs signal data even when
                # spreads are too thin to execute. Without this, signals never
                # accumulate → pre-fund never triggers → bot is stuck forever.
                # Only record if spread > fees (positive gross ROI)
                if gross_spread_pct > sum_fees_pct and self.signal_allocator:
                    raw_roi = gross_spread_pct - sum_fees_pct
                    self.signal_allocator.record_signal(
                        symbol=symbol, strategy='CROSS_EXCHANGE',
                        exchange=buy_ex, roi_pct=raw_roi
                    )
                
                # Prefilter: skip if spread < dynamic threshold (for EXECUTION only)
                if gross_spread_pct < dynamic_min_spread:
                    # Near-miss: spread is >50% of threshold (engine is working)
                    if gross_spread_pct > dynamic_min_spread * 0.5:
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

                # SPREAD PERSISTENCE: Only trade spreads that have persisted long enough
                # Engine 2.0: Uses level-specific persistence from CapitalManager
                # EXCEPTION: Skip persistence check for strong spreads (>3× cushion above fees)
                # These are almost certainly real and will disappear if we wait.
                min_hold_ms = cm.level.spread_persistence_ms if cm else self.MIN_SPREAD_HOLD_MS
                spread_excess = gross_spread_pct - dynamic_min_spread
                STRONG_SPREAD_MULTIPLIER = 3.0  # spread > 3× above threshold = strong
                strong_cushion = (cm.level.spread_threshold_above_fees * STRONG_SPREAD_MULTIPLIER) if cm else 0.18
                is_strong_spread = spread_excess > strong_cushion
                
                if not is_strong_spread:
                    spread_key = f"{symbol}:{buy_ex}->{sell_ex}"
                    now_ms = time.time() * 1000
                    if spread_key not in self._spread_first_seen:
                        self._spread_first_seen[spread_key] = now_ms
                        continue  # First time seeing this spread — wait for confirmation
                    elif now_ms - self._spread_first_seen[spread_key] < min_hold_ms:
                        continue  # Spread hasn't persisted long enough

                # LATENCY CHECK: Skip if combined exchange latency exceeds spread lifetime
                buy_latency = self._exchange_latency_ms.get(buy_ex, self.DEFAULT_EXCHANGE_LATENCY_MS)
                sell_latency = self._exchange_latency_ms.get(sell_ex, self.DEFAULT_EXCHANGE_LATENCY_MS)
                combined_latency = buy_latency + sell_latency
                if combined_latency > self.MAX_COMBINED_LATENCY_MS:
                    continue

                # §11 PAIR SCORING: Only trade top-scoring exchange pairs (after 20+ trades)
                if hft and settings.SEMI_HFT_ENABLED:
                    if not hft.is_top_pair(buy_ex, sell_ex):
                        continue  # Not a top-scoring pair, skip

                buy_avg, buy_filled = simulate_execution_from_book(asks, qty)
                sell_avg, sell_filled = simulate_execution_from_book(bids, qty)

                # Semi-HFT: Collect microstructure data (orderbook imbalance + lead-lag)
                if hft:
                    hft.update_orderbook_imbalance(symbol, buy_ex, bids, asks)
                    if top_bid > 0 and top_ask > 0:
                        hft.record_mid_price(buy_ex, symbol, (top_bid + top_ask) / 2)
                        hft.record_mid_price(sell_ex, symbol, (top_bid + top_ask) / 2)

                # §12 LEAD-LAG: Boost opportunities where buy is on lagging exchange
                lead_lag_boost = 0.0
                if hft and settings.SEMI_HFT_ENABLED:
                    all_exchanges = list(exmap.keys())
                    if hft.is_lead_lag_opportunity(symbol, buy_ex, sell_ex, all_exchanges):
                        # Favorable timing: sell exchange led the move, buy is still cheap
                        lead_lag_boost = settings.SEMI_HFT_LEAD_LAG_BOOST_PCT

                # VWAP SLIPPAGE CHECK: If VWAP price deviates >0.2% from top-of-book,
                # the order will eat deep into the book — reduce expected ROI
                buy_vwap_slippage = (buy_avg - top_ask) / top_ask * 100 if top_ask > 0 else 0
                sell_vwap_slippage = (top_bid - sell_avg) / top_bid * 100 if top_bid > 0 else 0
                total_book_slippage = buy_vwap_slippage + sell_vwap_slippage
                if total_book_slippage > self.MAX_VWAP_SLIPPAGE_PCT:
                    logger.debug(
                        f"📖 {symbol} {buy_ex}→{sell_ex}: Book slippage {total_book_slippage:.3f}% "
                        f"(buy VWAP +{buy_vwap_slippage:.3f}%, sell VWAP -{sell_vwap_slippage:.3f}%)"
                    )
                    continue  # Too much book depth erosion

                filled = min(buy_filled, sell_filled)
                if filled <= 0:
                    continue

                fees = (buy_avg * filled) * buy_fee + (sell_avg * filled) * sell_fee

                # GLOBAL SLIPPAGE BUFFER: deduct estimated slippage from ALL trades
                # With maker-first: buy side (limit) has ~0 slippage.
                # Only sell side (market) carries slippage: ~0.03% per leg.
                # Total buffer: 0.03% × 2 legs = 0.06% (conservative since buy is ~0)
                slippage_per_leg = settings.GLOBAL_SLIPPAGE_PER_LEG_PCT
                slippage_cost = (buy_avg * filled) * (slippage_per_leg * 2 / 100)

                gross = (sell_avg - buy_avg) * filled
                net = gross - fees - slippage_cost

                invested = buy_avg * filled
                roi_pct = (net / invested) * 100 if invested else 0.0
                # §12: Apply lead-lag timing boost
                roi_pct += lead_lag_boost
                
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
                    "asks_levels": asks[:10],  # For order slicing in executor
                    "bids_levels": bids[:10],
                }

                # Record EVERY positive-ROI finding to signal allocator BEFORE dedup
                # This is the PRIMARY source for coin selection — count ALL, not just deduped
                if roi_pct > 0 and self.signal_allocator:
                    self.signal_allocator.record_signal(
                        symbol=symbol, strategy='CROSS_EXCHANGE',
                        exchange=buy_ex, roi_pct=roi_pct
                    )

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
        
        # Sort by net profit, with MEXC-first tiebreaker (lower fees = more profit)
        def _sort_key(x):
            # Primary: net profit (higher is better)
            # Tiebreaker: prefer MEXC as buy-side (0.05% fee vs 0.10%+)
            mexc_bonus = 0.001 if x.get('buy_ex') in self._low_fee_exchanges else 0.0
            return x["net"] + mexc_bonus
        res.sort(key=_sort_key, reverse=True)
        
        # Limit to max concurrent opportunities
        if len(res) > settings.MAX_CONCURRENT_OPPORTUNITIES:
            logger.debug(f"Limiting to top {settings.MAX_CONCURRENT_OPPORTUNITIES} opportunities (found {len(res)})")
            res = res[:settings.MAX_CONCURRENT_OPPORTUNITIES]
        
        return res

    def update_exchange_latency(self, exchange: str, latency_ms: float):
        """Update rolling average latency for an exchange."""
        if latency_ms < 0 or latency_ms > 10000:
            return  # Ignore unreasonable values
        old = self._exchange_latency_ms.get(exchange, latency_ms)
        alpha = self.LATENCY_EMA_ALPHA
        self._exchange_latency_ms[exchange] = old * (1 - alpha) + latency_ms * alpha

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
            # CIRCUIT BREAKER: Check if trading is globally allowed before scanning
            if self.risk_manager:
                allowed, reason = self.risk_manager.is_trading_allowed()
                if not allowed:
                    logger.warning(f"⛔ CIRCUIT BREAKER: {reason}")
                    await asyncio.sleep(60)  # Wait 1 minute before checking again
                    continue

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
            
            # SYMBOL RANKING: Scan highest-signal symbols first.
            # This ensures the most profitable symbols get processed first in each cycle.
            SYMBOL_RANKING_WINDOW = 300  # Score symbols based on last 5 minutes of signals
            if self.signal_allocator and ready_symbols:
                ready_symbols.sort(
                    key=lambda s: self.signal_allocator._score_symbol_recent(s, SYMBOL_RANKING_WINDOW),
                    reverse=True
                )
            
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
                engine_trade_this_cycle = False  # ONE trade per scan cycle
                for o in opps:
                    # LIMIT: one trade per cycle to avoid balance race conditions
                    if engine_trade_this_cycle:
                        break
                    
                    # Skip trade execution if coins not yet positioned
                    # (signals are already recorded above in scan_once)
                    if self.signal_allocator and not self.signal_allocator.is_ready_to_trade():
                        continue
                    
                    # Only trade the pre-funded coin (skip other symbols)
                    if (self.signal_allocator and self.signal_allocator.get_current_coin()
                            and o.get('symbol') != self.signal_allocator.get_current_coin()):
                        continue
                    
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
                    
                    if result.get('status') in ('success', 'simulated'):
                        engine_trade_this_cycle = True
                    
                    # PRE-FUNDED MODEL: No JIT — too expensive.
                    # Instead, record the miss so rebalancer can top up if needed.
                    # With pre-funded inventory, most trades should have both sides ready.
                    if result.get('status') == 'blocked' and self.signal_allocator:
                        missed_symbol = result.get('missed_symbol', o.get('symbol', ''))
                        missed_exchange = result.get('missed_exchange', '')
                        missed_side = result.get('missed_side', 'sell')
                        self.signal_allocator.record_miss(missed_symbol, missed_exchange, missed_side)
                        # Also record the blocked opportunity as a signal for allocation
                        # This tells the allocator which coins are HOT (even if we can't trade yet)
                        self.signal_allocator.record_signal(
                            symbol=o.get('symbol', ''),
                            strategy='CROSS_EXCHANGE',
                            exchange=o.get('buy_ex', ''),
                            roi_pct=o.get('roi_pct', 0)
                        )
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
                        
                        # Engine 2.0: Record to CapitalManager for kill-logic + quality ranking
                        if self.capital_manager and result['status'] in ('success', 'simulated'):
                            # Estimate slippage from VWAP diff vs top-of-book
                            _buy_vwap_slip = abs(o.get('buy_avg', 0) - o.get('buy_price', o.get('buy_avg', 0)))
                            _sell_vwap_slip = abs(o.get('sell_price', o.get('sell_avg', 0)) - o.get('sell_avg', 0))
                            _top_ask = o.get('buy_price', o.get('buy_avg', 1))
                            _est_slippage = ((_buy_vwap_slip + _sell_vwap_slip) / max(_top_ask, 0.01)) * 100
                            self.capital_manager.record_trade_result(
                                symbol=o.get('symbol', ''),
                                buy_exchange=o.get('buy_ex', ''),
                                sell_exchange=o.get('sell_ex', ''),
                                net_profit_pct=o.get('roi_pct', 0),
                                slippage_pct=_est_slippage,
                            )
                        # Semi-HFT: Record trade result for pair scoring + kill-switches
                        if self.semi_hft:
                            self.semi_hft.record_trade_result(
                                buy_ex=o.get('buy_ex', ''),
                                sell_ex=o.get('sell_ex', ''),
                                symbol=o.get('symbol', ''),
                                net_profit_pct=o.get('roi_pct', 0),
                                slippage_pct=_est_slippage,
                                latency_ms=result.get('trade_info', {}).get('placement_time_ms', 200),
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
                        
                        # Compound reinvestment: split profits 70% reinvest / 30% reserve
                        if trade_successful and trade_profit > 0:
                            self._total_profit += trade_profit
                            self._reinvested_profit += trade_profit * self.PROFIT_REINVEST_PCT
                            self._reserved_profit += trade_profit * self.PROFIT_RESERVE_PCT
                        
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
                                # Decay epsilon periodically (every 50 trades)
                                self.rl_agent.episode_count += 1
                                if self.rl_agent.episode_count % 50 == 0:
                                    if self.rl_agent.epsilon > self.rl_agent.epsilon_min:
                                        self.rl_agent.epsilon *= self.rl_agent.epsilon_decay
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