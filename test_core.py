#!/usr/bin/env python3
"""
Comprehensive tests for the unified arbitrage bot.
Tests all core components: PriceStore, ArbitrageEngine, OrderExecutor,
14 strategies, exchange configs, and module integration.
"""
import sys
import os
import asyncio
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import settings


def test_settings():
    print("\n" + "=" * 60)
    print("TEST 1: Settings Module")
    print("=" * 60)
    assert hasattr(settings, 'DRY_RUN')
    assert hasattr(settings, 'MIN_NET_ROI_PCT')
    assert hasattr(settings, 'MAX_EXPOSURE_USDT')
    assert hasattr(settings, 'BYBIT_API_KEY')
    assert hasattr(settings, 'KUCOIN_API_KEY')
    assert hasattr(settings, 'HTX_API_KEY')
    assert hasattr(settings, 'MEXC_API_KEY')
    assert hasattr(settings, 'MAX_DAILY_LOSS')
    assert isinstance(settings.DRY_RUN, bool)
    assert settings.MIN_NET_ROI_PCT > 0
    print(f"  ✅ All settings accessible: DRY_RUN={settings.DRY_RUN}, ROI={settings.MIN_NET_ROI_PCT}%")


def test_price_store():
    print("\n" + "=" * 60)
    print("TEST 2: PriceStore")
    print("=" * 60)
    from core.price_store import PriceStore
    store = PriceStore()
    store.update("BTC-USDT", "Bybit", {
        "bids": [[50000.0, 1.0]], "asks": [[50001.0, 1.0]], "ts": time.time()
    })
    store.update("BTC-USDT", "KuCoin", {
        "bids": [[50100.0, 1.0]], "asks": [[50101.0, 1.0]], "ts": time.time()
    })
    snap = store.get("BTC-USDT")
    assert snap is not None
    assert "Bybit" in snap
    assert "KuCoin" in snap
    print(f"  ✅ PriceStore works: {len(snap)} exchanges for BTC-USDT")


def test_exchange_config():
    print("\n" + "=" * 60)
    print("TEST 3: Exchange Configuration")
    print("=" * 60)
    from core.exchange_config import EXCHANGE_PARAMS
    for ex in ["Bybit", "KuCoin", "HTX", "MEXC"]:
        assert ex in EXCHANGE_PARAMS, f"{ex} missing"
        assert "taker_fee" in EXCHANGE_PARAMS[ex]
        print(f"  ✅ {ex}: taker={EXCHANGE_PARAMS[ex]['taker_fee']*100:.3f}%")


def test_order_executor():
    print("\n" + "=" * 60)
    print("TEST 4: OrderExecutor (Dry Run)")
    print("=" * 60)
    from core.order_executor import OrderExecutor
    executor = OrderExecutor(dry_run=True)
    assert executor.dry_run is True
    can, reason = executor.can_trade("BTC-USDT")
    assert can is True
    opp = {
        'symbol': 'BTC-USDT', 'buy_ex': 'Bybit', 'sell_ex': 'KuCoin',
        'qty': 0.001, 'buy_avg': 50000.0, 'sell_avg': 50100.0,
        'net': 0.04, 'roi_pct': 0.08,
    }
    result = asyncio.get_event_loop().run_until_complete(executor.execute_arbitrage(opp))
    assert result['status'] == 'simulated'
    stats = executor.get_statistics()
    assert stats['total_orders'] == 1
    assert stats['total_profit'] > 0
    print(f"  ✅ Dry run: {stats['total_orders']} orders, ${stats['total_profit']:.4f} profit")


def test_arbitrage_engine():
    print("\n" + "=" * 60)
    print("TEST 5: ArbitrageEngine - scan_once")
    print("=" * 60)
    from core.price_store import PriceStore
    from core.arbitrage import ArbitrageEngine
    store = PriceStore()
    store.update("BTC-USDT", "Bybit", {
        "bids": [[50000.0, 1.0]], "asks": [[50000.0, 1.0]], "ts": time.time()
    })
    store.update("BTC-USDT", "KuCoin", {
        "bids": [[50100.0, 1.0]], "asks": [[50100.0, 1.0]], "ts": time.time()
    })
    engine = ArbitrageEngine(store, min_net_pct=0.01)
    opps = asyncio.get_event_loop().run_until_complete(engine.scan_once("BTC-USDT"))
    assert len(opps) > 0, "Should detect opportunity"
    best = opps[0]
    assert best['buy_ex'] == 'Bybit'
    assert best['sell_ex'] == 'KuCoin'
    assert best['net'] > 0
    print(f"  ✅ Found {len(opps)} opportunities: ${best['net']:.4f} ({best['roi_pct']:.3f}% ROI)")


def test_all_symbols():
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
            store.update(symbol, ex, {
                "bids": [[price, 10.0]], "asks": [[price, 10.0]], "ts": time.time()
            })
        engine = ArbitrageEngine(store, min_net_pct=0.01)
        opps = asyncio.get_event_loop().run_until_complete(engine.scan_once(symbol))
        if opps:
            detected += 1
    assert detected >= 5, f"Need at least 5 symbols with opps, got {detected}"
    print(f"  ✅ {detected}/{len(symbols)} symbols detected opportunities")


def test_all_modules_import():
    print("\n" + "=" * 60)
    print("TEST 7: All Modules Import (61 modules)")
    print("=" * 60)
    modules = [
        'core.price_store', 'core.arbitrage', 'core.order_executor', 'core.exchange_config',
        'core.balance_manager', 'core.risk_manager', 'core.state_manager', 'core.telegram_bot',
        'core.resource_monitor', 'core.triangular_arb', 'core.order_type_selector',
        'core.strategy_manager', 'core.rebalancer', 'core.startup_validator',
        'core.windows_optimizer', 'core.smart_capital_allocator', 'core.strategy_dispatcher',
        'infrastructure.health_monitor', 'infrastructure.alert_manager',
        'infrastructure.rate_limiter', 'infrastructure.circuit_breaker_enhanced',
        'infrastructure.metrics_collector', 'infrastructure.cache_manager',
        'infrastructure.config_manager', 'infrastructure.logger_manager',
        'analytics.trade_journal', 'analytics.performance_tracker', 'analytics.profit_attribution',
        'analytics.risk_analytics', 'analytics.backtest_engine', 'analytics.market_intelligence',
        'analytics.realtime_analytics', 'analytics.correlation_analyzer', 'analytics.custom_dashboard',
        'professional_features.flash_crash_protector', 'professional_features.wash_trading_filter',
        'professional_features.orderbook_imbalance_detector', 'professional_features.twap_engine',
        'professional_features.vwap_engine', 'professional_features.iceberg_order_detector',
        'professional_features.order_flow_tracker',
        'core.strategies.grid_trading', 'core.strategies.dca_strategy',
        'core.strategies.market_making', 'core.strategies.pairs_trading',
        'core.strategies.funding_rate_enhanced', 'core.strategies.volatility_arb',
        'core.strategies.index_arb', 'core.strategies.spread_betting',
        'strategies.momentum_strategy', 'strategies.breakout_strategy',
        'exchanges.bybit_ws', 'exchanges.kucoin_ws', 'exchanges.htx_ws', 'exchanges.mexc_ws',
        'exchanges.binance_ws', 'exchanges.rest_clients',
        'exchanges.rest_clients.bybit_client', 'exchanges.rest_clients.kucoin_client',
        'exchanges.rest_clients.htx_client', 'exchanges.rest_clients.mexc_client',
    ]
    ok = 0
    for mod in modules:
        try:
            __import__(mod)
            ok += 1
        except Exception as e:
            print(f"  ❌ {mod}: {e}")
    assert ok == len(modules), f"{ok}/{len(modules)} modules imported"
    print(f"  ✅ All {ok} modules imported successfully")


def test_balance_manager():
    print("\n" + "=" * 60)
    print("TEST 8: BalanceManager")
    print("=" * 60)
    from core.balance_manager import get_balance_manager
    bm = get_balance_manager(exchanges=["Bybit", "KuCoin", "HTX", "MEXC"])
    assert bm is not None
    bm.balances = {"Bybit": 100.0, "KuCoin": 50.0, "HTX": 75.0, "MEXC": 25.0}
    assert sum(bm.balances.values()) == 250.0
    print(f"  ✅ BalanceManager: {len(bm.balances)} exchanges, ${sum(bm.balances.values()):.2f} total")


def test_risk_manager():
    print("\n" + "=" * 60)
    print("TEST 9: RiskManager")
    print("=" * 60)
    from core.risk_manager import get_risk_manager
    rm = get_risk_manager()
    assert rm is not None
    can_trade = rm.can_trade()
    assert isinstance(can_trade, (bool, tuple))
    print(f"  ✅ RiskManager initialized, can_trade={can_trade}")


def test_state_manager():
    print("\n" + "=" * 60)
    print("TEST 10: StateManager")
    print("=" * 60)
    from core.state_manager import get_state_manager
    sm = get_state_manager()
    assert sm is not None
    print(f"  ✅ StateManager initialized")


def test_strategy_dispatcher():
    print("\n" + "=" * 60)
    print("TEST 11: Strategy Dispatcher (14 strategies)")
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
    print("\n" + "=" * 60)
    print("TEST 12: Professional Features (7 modules)")
    print("=" * 60)
    from professional_features.flash_crash_protector import FlashCrashProtector
    from professional_features.wash_trading_filter import WashTradingFilter
    from professional_features.orderbook_imbalance_detector import OrderBookImbalanceDetector
    from professional_features.twap_engine import TWAPEngine
    from professional_features.vwap_engine import VWAPEngine
    from professional_features.iceberg_order_detector import IcebergOrderDetector
    from professional_features.order_flow_tracker import OrderFlowTracker
    for cls in [FlashCrashProtector, WashTradingFilter, OrderBookImbalanceDetector,
                TWAPEngine, VWAPEngine, IcebergOrderDetector, OrderFlowTracker]:
        obj = cls()
        print(f"  ✅ {type(obj).__name__}")


def test_analytics():
    print("\n" + "=" * 60)
    print("TEST 13: Analytics (9 modules)")
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
    for cls in [TradeJournal, PerformanceTracker, ProfitAttributionAnalyzer,
                RiskAnalytics, BacktestEngine, MarketIntelligence, RealtimeAnalytics,
                CorrelationAnalyzer, CustomDashboard]:
        obj = cls()
        print(f"  ✅ {type(obj).__name__}")


def test_rest_clients():
    print("\n" + "=" * 60)
    print("TEST 14: REST Clients (4 exchanges)")
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


def test_e2e_arbitrage():
    print("\n" + "=" * 60)
    print("TEST 15: End-to-End Arbitrage Flow")
    print("=" * 60)
    from core.price_store import PriceStore
    from core.arbitrage import ArbitrageEngine
    from core.order_executor import OrderExecutor
    store = PriceStore()
    executor = OrderExecutor(dry_run=True)
    engine = ArbitrageEngine(store, min_net_pct=0.01, executor=executor)
    store.update("ETH-USDT", "HTX", {
        "bids": [[3000.0, 10.0]], "asks": [[3000.0, 10.0]], "ts": time.time()
    })
    store.update("ETH-USDT", "MEXC", {
        "bids": [[3010.0, 10.0]], "asks": [[3010.0, 10.0]], "ts": time.time()
    })
    opps = asyncio.get_event_loop().run_until_complete(engine.scan_once("ETH-USDT"))
    assert len(opps) > 0
    result = asyncio.get_event_loop().run_until_complete(executor.execute_arbitrage(opps[0]))
    assert result['status'] == 'simulated'
    stats = executor.get_statistics()
    assert stats['total_orders'] >= 1
    assert stats['total_profit'] > 0
    print(f"  ✅ E2E: found opportunity, executed, profit=${stats['total_profit']:.4f}")


if __name__ == "__main__":
    tests = [
        test_settings, test_price_store, test_exchange_config, test_order_executor,
        test_arbitrage_engine, test_all_symbols, test_all_modules_import,
        test_balance_manager, test_risk_manager, test_state_manager,
        test_strategy_dispatcher, test_professional_features, test_analytics,
        test_rest_clients, test_e2e_arbitrage,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n  ❌ FAILED: {e}")
    print(f"\n{'='*60}\nRESULTS: {passed} passed, {failed} failed out of {len(tests)} tests\n{'='*60}")
    if failed: sys.exit(1)
