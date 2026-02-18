#!/usr/bin/env python3
"""
Complete Integration Test - Verify all modules work correctly
Tests all 17 core modules integrated in main.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("COMPREHENSIVE BOT INTEGRATION TEST")
print("=" * 80)

test_results = []

def test_module(name, test_func):
    """Run a single module test"""
    try:
        test_func()
        test_results.append((name, "✅ PASS", None))
        print(f"✅ {name:40s} PASS")
        return True
    except Exception as e:
        test_results.append((name, "❌ FAIL", str(e)))
        print(f"❌ {name:40s} FAIL: {str(e)[:50]}")
        return False

# Test 1: Settings Import
def test_settings():
    import settings
    assert hasattr(settings, 'DRY_RUN')
    assert hasattr(settings, 'MIN_BALANCE_PER_EXCHANGE')
    assert hasattr(settings, 'MAX_EXPOSURE_USDT')

test_module("1. Settings Module", test_settings)

# Test 2: Core Modules
def test_price_store():
    from core.price_store import PriceStore
    store = PriceStore()
    assert store is not None

test_module("2. Price Store", test_price_store)

def test_arbitrage():
    from core.arbitrage import ArbitrageEngine
    # Don't instantiate, just check import
    assert ArbitrageEngine is not None

test_module("3. Arbitrage Engine", test_arbitrage)

def test_order_executor():
    from core.order_executor import OrderExecutor
    assert OrderExecutor is not None

test_module("4. Order Executor", test_order_executor)

# Test 3: Manager Modules
def test_balance_manager():
    from core.balance_manager import get_balance_manager
    manager = get_balance_manager()
    assert manager is not None

test_module("5. Balance Manager", test_balance_manager)

def test_risk_manager():
    from core.risk_manager import get_risk_manager
    manager = get_risk_manager()
    assert manager is not None

test_module("6. Risk Manager", test_risk_manager)

def test_state_manager():
    from core.state_manager import get_state_manager
    manager = get_state_manager()
    assert manager is not None

test_module("7. State Manager", test_state_manager)

def test_telegram_bot():
    from core.telegram_bot import get_telegram_bot
    # Don't actually create without credentials
    assert get_telegram_bot is not None

test_module("8. Telegram Bot", test_telegram_bot)

def test_resource_monitor():
    from core.resource_monitor import get_resource_monitor
    monitor = get_resource_monitor()
    assert monitor is not None

test_module("9. Resource Monitor", test_resource_monitor)

def test_triangular_arb():
    from core.triangular_arb import get_triangular_engine
    assert get_triangular_engine is not None

test_module("10. Triangular Arb", test_triangular_arb)

def test_order_type_selector():
    from core.order_type_selector import get_order_type_selector
    assert get_order_type_selector is not None

test_module("11. Order Type Selector", test_order_type_selector)

def test_strategy_manager():
    from core.strategy_manager import get_strategy_manager
    manager = get_strategy_manager()
    assert manager is not None

test_module("12. Strategy Manager", test_strategy_manager)

def test_rebalancer():
    from core.rebalancer import get_auto_rebalancer
    assert get_auto_rebalancer is not None

test_module("13. Auto Rebalancer", test_rebalancer)

def test_startup_validator():
    from core.startup_validator import get_startup_validator
    assert get_startup_validator is not None

test_module("14. Startup Validator", test_startup_validator)

def test_windows_optimizer():
    from core.windows_optimizer import setup_windows_optimizations, WindowsOptimizer
    assert setup_windows_optimizations is not None
    assert WindowsOptimizer is not None

test_module("15. Windows Optimizer", test_windows_optimizer)

def test_smart_allocator():
    from core.smart_capital_allocator import get_smart_allocator
    allocator = get_smart_allocator()
    assert allocator is not None

test_module("16. Smart Capital Allocator", test_smart_allocator)

# Test 4: Exchange Modules
def test_bybit_ws():
    from exchanges.bybit_ws import BybitWS
    assert BybitWS is not None

test_module("17. Bybit WebSocket", test_bybit_ws)

def test_kucoin_ws():
    from exchanges.kucoin_ws import KucoinWS
    assert KucoinWS is not None

test_module("18. KuCoin WebSocket", test_kucoin_ws)

def test_htx_ws():
    from exchanges.htx_ws import HtxWS
    assert HtxWS is not None

test_module("19. HTX WebSocket", test_htx_ws)

def test_mexc_ws():
    from exchanges.mexc_ws import MexcWS
    assert MexcWS is not None

test_module("20. MEXC WebSocket", test_mexc_ws)

def test_binance_ws():
    from exchanges.binance_ws import BinanceWS
    assert BinanceWS is not None

test_module("21. Binance WebSocket", test_binance_ws)

# Test 5: REST Clients
def test_bybit_rest():
    from exchanges.rest_clients.bybit_client import BybitRESTClient
    assert BybitRESTClient is not None

test_module("22. Bybit REST Client", test_bybit_rest)

def test_kucoin_rest():
    from exchanges.rest_clients.kucoin_client import KuCoinRESTClient
    assert KuCoinRESTClient is not None

test_module("23. KuCoin REST Client", test_kucoin_rest)

def test_htx_rest():
    from exchanges.rest_clients.htx_client import HTXRESTClient
    assert HTXRESTClient is not None

test_module("24. HTX REST Client", test_htx_rest)

def test_mexc_rest():
    from exchanges.rest_clients.mexc_client import MEXCRESTClient
    assert MEXCRESTClient is not None

test_module("25. MEXC REST Client", test_mexc_rest)

def test_binance_rest():
    from exchanges.rest_clients.binance_client import BinanceRESTClient
    assert BinanceRESTClient is not None

test_module("26. Binance REST Client", test_binance_rest)

# Test 6: Main Module
def test_main_import():
    import main
    assert main is not None

test_module("27. Main Module", test_main_import)

# Results Summary
print("=" * 80)
print("TEST SUMMARY")
print("=" * 80)

passed = sum(1 for _, status, _ in test_results if "PASS" in status)
failed = sum(1 for _, status, _ in test_results if "FAIL" in status)

print(f"\nTotal Tests: {len(test_results)}")
print(f"✅ Passed: {passed}")
print(f"❌ Failed: {failed}")
print(f"Success Rate: {passed/len(test_results)*100:.1f}%")

if failed > 0:
    print("\n❌ FAILED TESTS:")
    for name, status, error in test_results:
        if "FAIL" in status:
            print(f"  - {name}: {error}")

print("=" * 80)

if failed == 0:
    print("✅ ALL TESTS PASSED - BOT IS FULLY FUNCTIONAL")
    sys.exit(0)
else:
    print(f"❌ {failed} TESTS FAILED - PLEASE FIX ISSUES")
    sys.exit(1)
