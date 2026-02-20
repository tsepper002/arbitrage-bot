#!/usr/bin/env python3
"""
Comprehensive tests for the unified arbitrage bot.
Tests all 200+ modules, 14 strategies, E2E flow.
"""
import sys, os, asyncio, time, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import settings

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


def test_settings():
    """TEST 1: Settings Module"""
    print("\n" + "=" * 60)
    print("TEST 1: Settings Module")
    print("=" * 60)
    for attr in ['DRY_RUN', 'MIN_NET_ROI_PCT', 'MAX_EXPOSURE_USDT', 'SAFETY_FACTOR',
                 'BYBIT_API_KEY', 'KUCOIN_API_KEY', 'HTX_API_KEY', 'MEXC_API_KEY',
                 'MAX_DAILY_LOSS', 'SCAN_INTERVAL_SEC', 'TRADING_SYMBOLS']:
        assert hasattr(settings, attr), f"Missing: {attr}"
    assert isinstance(settings.DRY_RUN, bool)
    print(f"  ✅ All settings: DRY_RUN={settings.DRY_RUN}, ROI={settings.MIN_NET_ROI_PCT}%")


def test_price_store():
    """TEST 2: PriceStore (async API)"""
    print("\n" + "=" * 60)
    print("TEST 2: PriceStore")
    print("=" * 60)
    from core.price_store import PriceStore
    store = PriceStore()
    # Use async update_levels API
    loop.run_until_complete(store.update_levels("Bybit", "BTC-USDT",
        bids_levels=[(50000.0, 1.0)], asks_levels=[(50001.0, 1.0)]))
    loop.run_until_complete(store.update_levels("KuCoin", "BTC-USDT",
        bids_levels=[(50100.0, 1.0)], asks_levels=[(50101.0, 1.0)]))
    snap = store.snapshot()
    assert "BTC-USDT" in snap
    assert "Bybit" in snap["BTC-USDT"] and "KuCoin" in snap["BTC-USDT"]
    print(f"  ✅ PriceStore: {len(snap['BTC-USDT'])} exchanges for BTC-USDT")


def test_exchange_config():
    """TEST 3: Exchange Configuration"""
    print("\n" + "=" * 60)
    print("TEST 3: Exchange Configuration")
    print("=" * 60)
    from core.exchange_config import EXCHANGE_PARAMS
    for ex in ["Bybit", "KuCoin", "HTX", "MEXC"]:
        assert ex in EXCHANGE_PARAMS and "taker" in EXCHANGE_PARAMS[ex]
        print(f"  ✅ {ex}: taker={EXCHANGE_PARAMS[ex]['taker']*100:.3f}%")


def test_order_executor():
    """TEST 4: OrderExecutor Dry Run"""
    print("\n" + "=" * 60)
    print("TEST 4: OrderExecutor (Dry Run)")
    print("=" * 60)
    from core.order_executor import OrderExecutor
    executor = OrderExecutor(dry_run=True)
    assert executor.dry_run is True
    opp = {
        'symbol': 'BTC-USDT', 'buy_ex': 'Bybit', 'sell_ex': 'KuCoin',
        'qty': 0.001, 'buy_avg': 50000.0, 'sell_avg': 50100.0,
        'net': 0.04, 'roi_pct': 0.08,
    }
    result = loop.run_until_complete(executor.execute_arbitrage(opp))
    assert result['status'] == 'simulated'
    stats = executor.get_statistics()
    assert stats['total_orders'] == 1 and stats['total_profit'] > 0
    print(f"  ✅ Dry run: {stats['total_orders']} orders, ${stats['total_profit']:.4f}")


def test_arbitrage_engine():
    """TEST 5: ArbitrageEngine scan_once"""
    print("\n" + "=" * 60)
    print("TEST 5: ArbitrageEngine - scan_once")
    print("=" * 60)
    from core.price_store import PriceStore
    from core.arbitrage import ArbitrageEngine
    store = PriceStore()
    # Use larger spread to ensure detection after fees (0.1% + 0.1% = 0.2%)
    loop.run_until_complete(store.update_levels("Bybit", "BTC-USDT",
        bids_levels=[(50000.0, 1.0)], asks_levels=[(50000.0, 1.0)]))
    loop.run_until_complete(store.update_levels("KuCoin", "BTC-USDT",
        bids_levels=[(50200.0, 1.0)], asks_levels=[(50200.0, 1.0)]))
    engine = ArbitrageEngine(store, min_net_pct=0.01)
    opps = loop.run_until_complete(engine.scan_once("BTC-USDT"))
    assert len(opps) > 0
    best = opps[0]
    assert best['net'] > 0
    print(f"  ✅ Found {len(opps)} opps: ${best['net']:.4f} ({best['roi_pct']:.3f}% ROI)")


def test_all_symbols():
    """TEST 6: All 10 Symbols × 4 Exchanges"""
    print("\n" + "=" * 60)
    print("TEST 6: All 10 Symbols × 4 Exchanges")
    print("=" * 60)
    from core.price_store import PriceStore
    from core.arbitrage import ArbitrageEngine
    symbols = settings.TRADING_SYMBOLS
    exchanges = ["Bybit", "KuCoin", "HTX", "MEXC"]
    base_prices = {
        "BTC-USDT": 50000, "ETH-USDT": 3000, "SOL-USDT": 100,
        "BNB-USDT": 300, "XRP-USDT": 0.5, "DOGE-USDT": 0.1,
        "LTC-USDT": 80, "ADA-USDT": 0.4, "MATIC-USDT": 0.8, "DOT-USDT": 6,
    }
    detected = 0
    for symbol in symbols:
        store = PriceStore()
        base = base_prices.get(symbol, 100)
        for i, ex in enumerate(exchanges):
            price = base * (1 + i * 0.002)
            loop.run_until_complete(store.update_levels(ex, symbol,
                bids_levels=[(price, 10.0)], asks_levels=[(price, 10.0)]))
        engine = ArbitrageEngine(store, min_net_pct=0.01)
        opps = loop.run_until_complete(engine.scan_once(symbol))
        if opps:
            detected += 1
    assert detected >= 5
    print(f"  ✅ {detected}/{len(symbols)} symbols detected opportunities")


def test_all_modules_import():
    """TEST 7: All 200 Modules Import"""
    print("\n" + "=" * 60)
    print("TEST 7: All 200+ Modules Import")
    print("=" * 60)
    py_files = sorted(glob.glob('**/*.py', recursive=True))
    modules = set()
    for f in py_files:
        if '__pycache__' in f or 'test_' in f or f in ('main.py', 'engine.py'):
            continue
        mod = f.replace('/', '.').replace('.py', '')
        if mod.endswith('.__init__'):
            mod = mod[:-9]
        modules.add(mod)
    ok = 0; errors = []
    for mod in sorted(modules):
        try:
            __import__(mod)
            ok += 1
        except Exception as e:
            errors.append(f'{mod}: {e}')
    assert len(errors) == 0, f"{len(errors)} failed: {errors[:3]}"
    print(f"  ✅ All {ok} modules imported successfully")


def test_core_managers():
    """TEST 8: Core Managers"""
    print("\n" + "=" * 60)
    print("TEST 8: Core Managers")
    print("=" * 60)
    from core.balance_manager import get_balance_manager
    from core.risk_manager import get_risk_manager
    from core.state_manager import get_state_manager
    bm = get_balance_manager()
    assert bm is not None
    bm.balances = {"Bybit": 100.0, "KuCoin": 50.0, "HTX": 75.0, "MEXC": 25.0}
    assert sum(bm.balances.values()) == 250.0
    print(f"  ✅ BalanceManager: 4 exchanges, $250")
    rm = get_risk_manager()
    assert rm is not None
    print(f"  ✅ RiskManager: initialized")
    sm = get_state_manager()
    assert sm is not None
    print(f"  ✅ StateManager: initialized")


def test_strategy_dispatcher():
    """TEST 9: Strategy Dispatcher"""
    print("\n" + "=" * 60)
    print("TEST 9: Strategy Dispatcher (14 strategies)")
    print("=" * 60)
    from core.strategy_dispatcher import StrategyDispatcher
    class MockBot:
        def __init__(self):
            for attr in ['store', 'engine', 'triangular_engine', 'order_type_selector',
                         'strategy_manager', 'grid_strategy', 'dca_strategy',
                         'market_making_strategy', 'pairs_strategy', 'funding_strategy',
                         'vol_arb_strategy', 'index_arb_strategy', 'spread_strategy',
                         'momentum_strategy', 'breakout_strategy', 'flash_crash_protector',
                         'wash_trading_filter', 'orderbook_imbalance_detector']:
                setattr(self, attr, None)
    dispatcher = StrategyDispatcher(MockBot())
    assert len(dispatcher.strategy_stats) == 14
    print(f"  ✅ StrategyDispatcher: {len(dispatcher.strategy_stats)} strategies")
    for name in dispatcher.strategy_stats:
        print(f"    - {name}")


def test_professional_features():
    """TEST 10: Professional Features"""
    print("\n" + "=" * 60)
    print("TEST 10: Professional Features")
    print("=" * 60)
    from professional_features.flash_crash_protector import FlashCrashProtector
    from professional_features.wash_trading_filter import WashTradingFilter
    from professional_features.orderbook_imbalance_detector import OrderBookImbalanceDetector
    from professional_features.twap_engine import TWAPEngine
    from professional_features.vwap_engine import VWAPEngine
    from professional_features.iceberg_order_detector import IcebergOrderDetector
    from professional_features.order_flow_tracker import OrderFlowTracker
    from professional_features.cross_margining_manager import CrossMarginingManager
    from professional_features.funding_rate_predictor import FundingRatePredictor
    from professional_features.smart_order_router import SmartOrderRouter
    from professional_features.tape_reader import TapeReader
    from professional_features.sentiment_analyzer import SentimentAnalyzer
    from professional_features.multi_leg_executor import MultiLegExecutor

    # Most can be instantiated with no args
    for cls in [FlashCrashProtector, WashTradingFilter, OrderBookImbalanceDetector,
                TWAPEngine, VWAPEngine, IcebergOrderDetector, OrderFlowTracker,
                CrossMarginingManager, FundingRatePredictor,
                SmartOrderRouter, TapeReader, SentimentAnalyzer]:
        obj = cls()
        print(f"  ✅ {type(obj).__name__}")
    # MultiLegExecutor needs exchange_clients arg
    mle = MultiLegExecutor(exchange_clients={})
    print(f"  ✅ {type(mle).__name__}")


def test_analytics():
    """TEST 11: Analytics"""
    print("\n" + "=" * 60)
    print("TEST 11: Analytics")
    print("=" * 60)
    from analytics.trade_journal import TradeJournal
    from analytics.performance_tracker import PerformanceTracker
    from analytics.profit_attribution import ProfitAttributionAnalyzer
    from analytics.risk_analytics import RiskAnalytics
    from analytics.backtest_engine import BacktestEngine
    from analytics.market_intelligence import MarketIntelligence
    from analytics.realtime_analytics import RealtimeAnalytics
    from analytics.correlation_analyzer import CorrelationAnalyzer
    from analytics.custom_dashboard import CustomDashboard
    from analytics.report_generator import ReportGenerator
    from analytics.advanced_charting import AdvancedCharting
    from analytics.cohort_analysis import CohortAnalyzer

    for cls in [TradeJournal, PerformanceTracker, ProfitAttributionAnalyzer,
                RiskAnalytics, BacktestEngine, MarketIntelligence, RealtimeAnalytics,
                CorrelationAnalyzer, CustomDashboard, ReportGenerator,
                AdvancedCharting, CohortAnalyzer]:
        obj = cls()
        print(f"  ✅ {type(obj).__name__}")


def test_ml_modules():
    """TEST 12: ML Modules"""
    print("\n" + "=" * 60)
    print("TEST 12: ML Modules (11)")
    print("=" * 60)
    from ml.auto_parameter_optimizer import AutoParameterOptimizer
    from ml.auto_parameter_tuner import AutoParameterTuner
    from ml.market_adaptive_strategy import MarketAdaptiveStrategy
    from ml.market_regime_detector import MarketRegimeDetector
    from ml.ml_model_trainer import MLModelTrainer
    from ml.ml_spread_predictor import MLSpreadPredictor
    from ml.neural_network_predictor import NeuralNetworkPredictor
    from ml.pattern_recognition import PatternRecognition
    from ml.reinforcement_learning_agent import ReinforcementLearningAgent
    from ml.slippage_predictor import SlippagePredictor
    from ml.volatility_forecaster import VolatilityForecaster
    for cls in [AutoParameterOptimizer, AutoParameterTuner, MarketAdaptiveStrategy,
                MarketRegimeDetector, MLModelTrainer, MLSpreadPredictor,
                NeuralNetworkPredictor, PatternRecognition, ReinforcementLearningAgent,
                SlippagePredictor, VolatilityForecaster]:
        obj = cls()
        print(f"  ✅ {type(obj).__name__}")


def test_rest_clients():
    """TEST 13: REST Clients"""
    print("\n" + "=" * 60)
    print("TEST 13: REST Clients (4 exchanges)")
    print("=" * 60)
    from exchanges.rest_clients.bybit_client import BybitRESTClient
    from exchanges.rest_clients.kucoin_client import KuCoinRESTClient
    from exchanges.rest_clients.htx_client import HTXRESTClient
    from exchanges.rest_clients.mexc_client import MEXCRESTClient
    BybitRESTClient(api_key="test", api_secret="test")
    KuCoinRESTClient(api_key="test", api_secret="test", passphrase="test")
    HTXRESTClient(api_key="test", api_secret="test")
    MEXCRESTClient(api_key="test", api_secret="test")
    print(f"  ✅ All 4 REST clients initialized")


def test_advanced_core():
    """TEST 14: Advanced Core Modules"""
    print("\n" + "=" * 60)
    print("TEST 14: Advanced Core Modules")
    print("=" * 60)
    from core.depth_arbitrage import DepthArbitrage
    from core.statistical_arbitrage import StatisticalArbitrage
    from core.fee_optimizer import FeeOptimizer
    from core.slippage_predictor import SlippagePredictor
    from core.cross_chain_arbitrage import CrossChainArbitrage
    from core.funding_arbitrage import FundingArbitrage
    from core.liquidity_mining import LiquidityMining
    from core.news_trading import NewsTrading
    from core.circuit_breaker import CircuitBreaker
    from core.connection_pool import ConnectionPool

    # Most can be instantiated with no args, cross_chain needs bridges
    for cls in [DepthArbitrage, StatisticalArbitrage, FeeOptimizer,
                SlippagePredictor,
                LiquidityMining, NewsTrading, CircuitBreaker, ConnectionPool]:
        obj = cls()
        print(f"  ✅ {type(obj).__name__}")
    # These need constructor args
    fa = FundingArbitrage(rest_clients={}, balance_manager=None)
    print(f"  ✅ {type(fa).__name__}")
    cca = CrossChainArbitrage(bridges={})
    print(f"  ✅ {type(cca).__name__}")


def test_e2e_arbitrage():
    """TEST 15: End-to-End Arbitrage Flow"""
    print("\n" + "=" * 60)
    print("TEST 15: End-to-End Arbitrage Flow")
    print("=" * 60)
    from core.price_store import PriceStore
    from core.arbitrage import ArbitrageEngine
    from core.order_executor import OrderExecutor
    store = PriceStore()
    executor = OrderExecutor(dry_run=True)
    engine = ArbitrageEngine(store, min_net_pct=0.01, executor=executor)
    loop.run_until_complete(store.update_levels("HTX", "ETH-USDT",
        bids_levels=[(3000.0, 10.0)], asks_levels=[(3000.0, 10.0)]))
    loop.run_until_complete(store.update_levels("MEXC", "ETH-USDT",
        bids_levels=[(3010.0, 10.0)], asks_levels=[(3010.0, 10.0)]))
    opps = loop.run_until_complete(engine.scan_once("ETH-USDT"))
    assert len(opps) > 0
    result = loop.run_until_complete(executor.execute_arbitrage(opps[0]))
    assert result['status'] == 'simulated'
    stats = executor.get_statistics()
    assert stats['total_orders'] >= 1 and stats['total_profit'] > 0
    print(f"  ✅ E2E: opportunity → execution → profit=${stats['total_profit']:.4f}")


if __name__ == "__main__":
    tests = [
        test_settings, test_price_store, test_exchange_config, test_order_executor,
        test_arbitrage_engine, test_all_symbols, test_all_modules_import,
        test_core_managers, test_strategy_dispatcher, test_professional_features,
        test_analytics, test_ml_modules, test_rest_clients, test_advanced_core,
        test_e2e_arbitrage,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n  ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
    print(f"\n{'='*60}\nRESULTS: {passed} passed, {failed} failed out of {len(tests)}\n{'='*60}")
    if failed:
        sys.exit(1)
