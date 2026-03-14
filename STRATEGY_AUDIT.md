# 📊 STRATEGY AUDIT — Honest Assessment (14 Strategies)

**Balance assumption:** $20 USDT across 4 exchanges ($5 per exchange, ~$3 tradeable after $2 reserve)  
**All profits are ESTIMATES — real results depend on market conditions, spreads, and execution speed**

---

## ⚡ FAST STRATEGIES (scan every 0.5s)

### Strategy 1: CROSS_EXCHANGE
- **File:** `core/arbitrage.py` → `ArbitrageEngine.scan_once()`
- **What it does:** Compares bid price on exchange A vs ask price on exchange B. If `bid_A > ask_B + fees`, buy on B and sell on A simultaneously.
- **Code correct?** ✅ YES — Full orderbook simulation (`simulate_execution_from_book`), proper fee deduction for each exchange, exposure cap, safety factor, deduplication.
- **Scanner works?** ✅ YES — Scans every 0.5s for all 10 symbols across all exchange pairs.
- **Executes trades?** ✅ YES — Only strategy that was always executing via `executor.execute_arbitrage()`.
- **Improvements needed?** ❌ None critical. Code is production-ready.
- **Expected daily profit ($20 capital):** $0.01–$0.05/day. Spreads on major pairs (BTC, ETH) are very tight. With $3 trade size, a 0.05% net ROI gives $0.0015 per trade. ~10-30 trades/day possible.

### Strategy 2: TRIANGULAR
- **File:** `core/strategy_dispatcher.py` → `scan_fast()` lines 177-241
- **What it does:** Cross-exchange triangular arbitrage. Checks 5 pair combinations (BTC/ETH, BTC/SOL, etc.) across exchanges. Formula: `roi = (bid_b_ex2 × bid_a_ex1) / (ask_a_ex2 × ask_b_ex1) × (1-fee)³ - 1`
- **Code correct?** ✅ YES — Asymmetric check (forward ≠ reverse), uses exchange-specific fees, MIN_NET_ROI filter.
- **Scanner works?** ✅ YES — Scans every 0.5s.
- **Executes trades?** ✅ YES — **FIXED:** Now routes profitable signals to OrderExecutor via `_build_trade_from_signal()`.
- **Improvements needed?** ⚠️ Could add multi-leg execution (currently executes as best buy→sell pair from signal). True 3-leg simultaneous execution would need additional logic.
- **Expected daily profit ($20 capital):** $0.005–$0.02/day. Cross-exchange implied rate discrepancies are rare with $3 trades.

### Strategy 3: SMART_ORDER
- **File:** `core/strategy_dispatcher.py` → `scan_fast()` lines 242-261
- **What it does:** Detects when bid-ask spread is > 2× taker fee. Signals that limit orders would be more profitable than market orders.
- **Code correct?** ✅ YES — Correct spread/fee comparison.
- **Scanner works?** ✅ YES — Scans every 0.5s.
- **Executes trades?** ⚠️ ADVISORY — This is an order type signal, not a trade. It informs CROSS_EXCHANGE to prefer limit orders when spreads are wide.
- **Improvements needed?** Could integrate with OrderExecutor's order type selection.
- **Expected daily profit:** $0 directly (advisory signal that helps other strategies).

### Strategy 4: VOLATILITY
- **File:** `core/strategy_dispatcher.py` → `scan_fast()` lines 263-281
- **What it does:** Measures 10-tick price variance. Signals when volatility > 0.15% (high activity = more arb opportunities).
- **Code correct?** ✅ YES — Standard variance/std calculation.
- **Scanner works?** ✅ YES — Scans every 0.5s.
- **Executes trades?** ⚠️ ADVISORY — Signals market condition (used by regime detector to adjust MIN_ROI).
- **Improvements needed?** ❌ None — correctly serves as market condition input.
- **Expected daily profit:** $0 directly (helps CROSS_EXCHANGE adjust thresholds).

---

## 🐌 SLOW STRATEGIES (scan every 60s)

### Strategy 5: GRID_TRADING
- **File:** `core/strategy_dispatcher.py` → `_scan_grid_trading()` lines 332-366
- **Module:** `core/strategies/grid_trading.py`
- **What it does:** Checks if price deviates significantly from center (average). Signals grid rebalancing when deviation > 30% of range.
- **Code correct?** ⚠️ PARTIAL — Scanner detects when grid needs rebalancing, but doesn't actually place grid orders (buy below/sell above). The `GridTradingStrategy` class has `_analyze_and_trade()` but it's never called directly.
- **Scanner works?** ✅ YES — Correctly measures deviation from center.
- **Executes trades?** ⚠️ NEW: Routes through `_build_trade_from_signal()` but executes as cross-exchange arb, not true grid orders.
- **Improvements needed?** ⚠️ YES — Needs limit order placement for proper grid trading. Current implementation detects the signal but execution is simplified.
- **Expected daily profit ($20 capital):** $0.001–$0.01/day. Grid works best with larger capital ($100+) in ranging markets.

### Strategy 6: DCA (Dollar Cost Averaging)
- **File:** `core/strategy_dispatcher.py` → `_scan_dca()` lines 368-397
- **Module:** `core/strategies/dca_strategy.py`
- **What it does:** Compares current price to 20-period SMA. Signals buy when price dips > 1% below SMA.
- **Code correct?** ✅ YES — Standard dip-buying logic with SMA baseline.
- **Scanner works?** ✅ YES — Correctly calculates SMA and dip percentage.
- **Executes trades?** ✅ YES — **FIXED:** Routes buy signals through executor when dip_pct > 0.
- **Improvements needed?** ⚠️ Could add position tracking (how much already accumulated).
- **Expected daily profit ($20 capital):** $0.005–$0.03/day. DCA works over weeks/months, not daily. Short-term the buy signals provide entry timing for other strategies.

### Strategy 7: MARKET_MAKING
- **File:** `core/strategy_dispatcher.py` → `_scan_market_making()` lines 399-425
- **Module:** `core/strategies/market_making.py`
- **What it does:** Checks if bid-ask spread is wide enough (> min_spread 0.2%). Signals that placing both bid and ask orders would be profitable.
- **Code correct?** ✅ YES — Correct spread/threshold comparison.
- **Scanner works?** ✅ YES — Correctly measures spread.
- **Executes trades?** ⚠️ SIGNAL ONLY — True market making requires placing limit orders on both sides and managing inventory. Current execution simplified to cross-exchange.
- **Improvements needed?** ⚠️ YES — Needs bid/ask limit order placement for proper market making.
- **Expected daily profit ($20 capital):** $0.002–$0.01/day. Requires faster execution and larger capital.

### Strategy 8: PAIRS_TRADING
- **File:** `core/strategy_dispatcher.py` → `_scan_pairs_trading()` lines 427-473
- **Module:** `core/strategies/pairs_trading.py`
- **What it does:** Calculates z-score of BTC/ETH ratio. Signals when z > 2.0 (mean reversion opportunity).
- **Code correct?** ✅ YES — Standard z-score calculation, proper mean/std with 20+ data points.
- **Scanner works?** ✅ YES — Correctly identifies divergence.
- **Executes trades?** ✅ YES — **FIXED:** Routes z-score signals through executor.
- **Improvements needed?** ⚠️ True pairs trading requires being long one and short the other simultaneously. Current implementation buys the cheaper one.
- **Expected daily profit ($20 capital):** $0.001–$0.005/day. z-score > 2 signals are rare in correlated pairs.

### Strategy 9: FUNDING_RATE
- **File:** `core/strategy_dispatcher.py` → `_scan_funding_rate()` lines 475-517
- **What it does:** Detects price premium/discount > 0.3% between exchanges. Similar to cross-exchange arb but focused on persistent premium.
- **Code correct?** ✅ YES — Correct premium calculation vs average.
- **Scanner works?** ✅ YES — Checks all symbols across all exchanges.
- **Executes trades?** ✅ YES — **FIXED:** Routes premium signals through executor.
- **Improvements needed?** ⚠️ Note: This is SPOT premium, not futures funding rate. For true funding rate arb, need futures API access.
- **Expected daily profit ($20 capital):** $0.005–$0.02/day. 0.3%+ premiums are uncommon but when they happen, are quite profitable.

### Strategy 10: VOLATILITY_ARB
- **File:** `core/strategy_dispatcher.py` → `_scan_volatility_arb()` lines 519-565
- **What it does:** Detects when one exchange has 2× wider spread than another for the same symbol.
- **Code correct?** ✅ YES — Correct spread ratio comparison.
- **Scanner works?** ✅ YES — Compares spread across exchanges.
- **Executes trades?** ⚠️ SIGNAL ONLY — Identifying spread differences doesn't directly translate to a trade without market making capability.
- **Improvements needed?** ⚠️ Could be used to prefer exchanges with narrower spreads for execution.
- **Expected daily profit ($20 capital):** $0 directly (advisory).

### Strategy 11: INDEX_ARB
- **File:** `core/strategy_dispatcher.py` → `_scan_index_arb()` lines 567-607
- **What it does:** Compares BTC price on each exchange to composite average. Signals when deviation > 0.1%.
- **Code correct?** ✅ YES — Correct deviation calculation.
- **Scanner works?** ✅ YES — Checks BTC across all exchanges.
- **Executes trades?** ✅ YES — **FIXED:** Routes deviation signals through executor.
- **Improvements needed?** ❌ None — this is essentially cross-exchange arb with a different entry condition.
- **Expected daily profit ($20 capital):** $0.005–$0.02/day. Same as cross-exchange arb.

### Strategy 12: SPREAD_BETTING
- **File:** `core/strategy_dispatcher.py` → `_scan_spread_betting()` lines 609-652
- **Module:** `core/strategies/spread_betting.py`
- **What it does:** z-score on BTC-ETH spread history. Signals mean-reversion entry when z > 2.0.
- **Code correct?** ✅ YES — Standard z-score on spread time series.
- **Scanner works?** ✅ YES — Requires 30+ data points (fills up after ~30 minutes).
- **Executes trades?** ✅ YES — **FIXED:** Routes z-score signals through executor.
- **Improvements needed?** ❌ None critical.
- **Expected daily profit ($20 capital):** $0.001–$0.005/day. z-score > 2 signals are infrequent.

### Strategy 13: MOMENTUM
- **File:** `core/strategy_dispatcher.py` → `_scan_momentum()` lines 654-687
- **Module:** `strategies/momentum_strategy.py`
- **What it does:** Calculates RSI and strength indicator. Signals when RSI is extreme (overbought/oversold).
- **Code correct?** ✅ YES — Calls `MomentumStrategy.analyze()` which computes RSI.
- **Scanner works?** ✅ YES — Requires 20+ price history points.
- **Executes trades?** ✅ YES — **FIXED:** Routes strong signals (strength > 0.6) through executor.
- **Improvements needed?** ⚠️ Momentum is a trend-following strategy that works better in trending markets. Could add regime filter.
- **Expected daily profit ($20 capital):** $0.001–$0.01/day. Depends on market conditions.

### Strategy 14: BREAKOUT
- **File:** `core/strategy_dispatcher.py` → `_scan_breakout()` lines 689-723
- **Module:** `strategies/breakout_strategy.py`
- **What it does:** Detects price breakouts from recent ranges. Uses support/resistance levels.
- **Code correct?** ✅ YES — Calls `BreakoutStrategy.analyze()` with price and volume data.
- **Scanner works?** ✅ YES — Requires 50+ price history points (~50 minutes of data).
- **Executes trades?** ✅ YES — **FIXED:** Routes breakout signals through executor.
- **Improvements needed?** ⚠️ Uses price change as volume proxy (no real volume data from WebSocket). Real volume would improve accuracy.
- **Expected daily profit ($20 capital):** $0.001–$0.005/day. Breakouts are uncommon in a 24h window.

---

## 🧠 ML MODULES (Active in ArbitrageEngine)

| Module | File | Status | What it does |
|--------|------|--------|-------------|
| MarketRegimeDetector | `core/fee_optimizer.py` | ✅ ACTIVE | Detects CALM/VOLATILE/TRENDING market → adjusts MIN_ROI (×0.8 calm, ×1.5 volatile) |
| MLSpreadPredictor | `core/ml_spread_predictor.py` | ✅ ACTIVE | Observes and predicts cross-exchange spreads |
| FeeOptimizer | `core/fee_optimizer.py` | ✅ ACTIVE | Records trade fees, finds cheapest exchange per pair |
| AutoParameterOptimizer | `ml/auto_parameter_optimizer.py` | ✅ IMPORTED | Available for grid/random/Bayesian parameter tuning |

## 🛡️ PROFESSIONAL FEATURES (Active in ArbitrageEngine)

| Feature | File | Status | What it does |
|---------|------|--------|-------------|
| FlashCrashProtector | `professional_features/flash_crash_protector.py` | ✅ ACTIVE | Blocks trades during market crashes |
| WashTradingFilter | `professional_features/wash_trading_filter.py` | ✅ ACTIVE | Blocks suspicious volume patterns |
| OrderbookImbalanceDetector | `professional_features/orderbook_imbalance_detector.py` | ✅ ACTIVE | Adjusts ROI threshold based on buy/sell pressure |

---

## 💰 TOTAL ESTIMATED DAILY PROFIT ($20 capital, 4 exchanges)

| Strategy | Est. Daily Profit |
|----------|------------------|
| CROSS_EXCHANGE | $0.01–$0.05 |
| TRIANGULAR | $0.005–$0.02 |
| FUNDING_RATE | $0.005–$0.02 |
| INDEX_ARB | $0.005–$0.02 |
| DCA | $0.005–$0.03 |
| PAIRS_TRADING | $0.001–$0.005 |
| SPREAD_BETTING | $0.001–$0.005 |
| MOMENTUM | $0.001–$0.01 |
| BREAKOUT | $0.001–$0.005 |
| SMART_ORDER | Advisory |
| VOLATILITY | Advisory |
| VOLATILITY_ARB | Advisory |
| GRID_TRADING | $0.001–$0.01 |
| MARKET_MAKING | $0.002–$0.01 |
| **TOTAL** | **$0.04–$0.20/day** |

**⚠️ IMPORTANT CAVEATS:**
1. With $20 total capital, minimum order sizes on exchanges may block some trades ($5-10 USDT minimums)
2. Fees on small trades proportionally higher
3. Network latency on Windows can miss tight spreads
4. These estimates assume moderate market activity
5. **More capital = exponentially more profit** (arb scales linearly, but bigger capital accesses more liquidity levels and reduces per-trade fee impact)
6. At $100 capital: estimated $0.20–$1.00/day
7. At $1000 capital: estimated $2–$10/day
