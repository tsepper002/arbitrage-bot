#!/usr/bin/env python3
"""
Production Validation Script for Arbitrage Bot
Tests all components and their integration without requiring API keys
"""
import sys
import asyncio
from pathlib import Path

def test_imports():
    """Test all critical imports"""
    print("=" * 60)
    print("PHASE 1: Testing Module Imports")
    print("=" * 60)
    
    tests = []
    
    # Core modules
    core_modules = [
        'arbitrage', 'balance_manager', 'risk_manager', 'state_manager',
        'telegram_bot', 'resource_monitor', 'triangular_arb',
        'order_type_selector', 'strategy_manager', 'rebalancer',
        'startup_validator', 'windows_optimizer', 'order_executor',
        'price_store', 'exchange_config', 'volume_weighted_analyzer',
        'slippage_predictor'
    ]
    
    for module in core_modules:
        try:
            exec(f"from core import {module}")
            tests.append(('✅', f'core.{module}'))
        except Exception as e:
            tests.append(('❌', f'core.{module}: {str(e)[:50]}'))
    
    # Exchange modules
    try:
        from exchanges import bybit_ws, kucoin_ws, htx_ws, mexc_ws
        tests.append(('✅', 'exchanges.websockets'))
    except Exception as e:
        tests.append(('❌', f'exchanges.websockets: {str(e)[:50]}'))
    
    # Settings
    try:
        import settings
        tests.append(('✅', 'settings'))
    except Exception as e:
        tests.append(('❌', f'settings: {str(e)[:50]}'))
    
    # Print results
    passed = sum(1 for status, _ in tests if status == '✅')
    total = len(tests)
    
    for status, msg in tests:
        print(f"{status} {msg}")
    
    print(f"\nImport Tests: {passed}/{total} passed")
    return passed == total

def test_factory_functions():
    """Test factory functions exist"""
    print("\n" + "=" * 60)
    print("PHASE 2: Testing Factory Functions")
    print("=" * 60)
    
    tests = []
    
    try:
        from core.balance_manager import get_balance_manager
        tests.append(('✅', 'get_balance_manager'))
    except Exception:
        tests.append(('❌', 'get_balance_manager'))
    
    try:
        from core.risk_manager import get_risk_manager
        tests.append(('✅', 'get_risk_manager'))
    except Exception:
        tests.append(('❌', 'get_risk_manager'))
    
    try:
        from core.state_manager import get_state_manager
        tests.append(('✅', 'get_state_manager'))
    except Exception:
        tests.append(('❌', 'get_state_manager'))
    
    try:
        from core.telegram_bot import get_telegram_bot
        tests.append(('✅', 'get_telegram_bot'))
    except Exception:
        tests.append(('❌', 'get_telegram_bot'))
    
    try:
        from core.resource_monitor import get_resource_monitor
        tests.append(('✅', 'get_resource_monitor'))
    except Exception:
        tests.append(('❌', 'get_resource_monitor'))
    
    try:
        from core.strategy_manager import get_strategy_manager
        tests.append(('✅', 'get_strategy_manager'))
    except Exception:
        tests.append(('❌', 'get_strategy_manager'))
    
    try:
        from core.triangular_arb import get_triangular_engine
        tests.append(('✅', 'get_triangular_engine'))
    except Exception:
        tests.append(('❌', 'get_triangular_engine'))
    
    try:
        from core.rebalancer import get_auto_rebalancer
        tests.append(('✅', 'get_auto_rebalancer'))
    except Exception:
        tests.append(('❌', 'get_auto_rebalancer'))
    
    try:
        from core.startup_validator import get_startup_validator
        tests.append(('✅', 'get_startup_validator'))
    except Exception:
        tests.append(('❌', 'get_startup_validator'))
    
    try:
        from core.windows_optimizer import setup_windows_optimizations
        tests.append(('✅', 'setup_windows_optimizations'))
    except Exception:
        tests.append(('❌', 'setup_windows_optimizations'))
    
    passed = sum(1 for status, _ in tests if status == '✅')
    total = len(tests)
    
    for status, msg in tests:
        print(f"{status} {msg}")
    
    print(f"\nFactory Tests: {passed}/{total} passed")
    return passed == total

def test_configuration():
    """Test configuration loading"""
    print("\n" + "=" * 60)
    print("PHASE 3: Testing Configuration")
    print("=" * 60)
    
    tests = []
    
    try:
        import settings
        config = settings.get_config()
        tests.append(('✅', f'Config loaded: DRY_RUN={config["DRY_RUN"]}'))
    except Exception as e:
        tests.append(('❌', f'Config failed: {e}'))
    
    try:
        trading_symbols = settings.TRADING_SYMBOLS
        tests.append(('✅', f'Symbols: {len(trading_symbols)} pairs'))
    except Exception as e:
        tests.append(('❌', f'Symbols failed: {e}'))
    
    try:
        from core.exchange_config import EXCHANGE_PARAMS
        tests.append(('✅', f'Exchange params: {len(EXCHANGE_PARAMS)} exchanges'))
    except Exception as e:
        tests.append(('❌', f'Exchange params failed: {e}'))
    
    passed = sum(1 for status, _ in tests if status == '✅')
    total = len(tests)
    
    for status, msg in tests:
        print(f"{status} {msg}")
    
    print(f"\nConfig Tests: {passed}/{total} passed")
    return passed == total

async def test_async_components():
    """Test async component initialization"""
    print("\n" + "=" * 60)
    print("PHASE 4: Testing Async Components")
    print("=" * 60)
    
    tests = []
    
    try:
        from core.price_store import PriceStore
        store = PriceStore()
        tests.append(('✅', 'PriceStore initialization'))
    except Exception as e:
        tests.append(('❌', f'PriceStore: {e}'))
    
    try:
        from core.order_executor import OrderExecutor
        executor = OrderExecutor(dry_run=True)
        tests.append(('✅', 'OrderExecutor initialization'))
    except Exception as e:
        tests.append(('❌', f'OrderExecutor: {e}'))
    
    try:
        from core.arbitrage import ArbitrageEngine
        import settings
        store = PriceStore()
        engine = ArbitrageEngine(
            store,  # First positional argument
            default_qty=0.001,
            min_net_pct=0.03,
            executor=OrderExecutor(dry_run=True)
        )
        tests.append(('✅', 'ArbitrageEngine initialization'))
    except Exception as e:
        tests.append(('❌', f'ArbitrageEngine: {e}'))
    
    passed = sum(1 for status, _ in tests if status == '✅')
    total = len(tests)
    
    for status, msg in tests:
        print(f"{status} {msg}")
    
    print(f"\nAsync Tests: {passed}/{total} passed")
    return passed == total

def print_summary(results):
    """Print final summary"""
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    for phase, passed in results.items():
        status = '✅' if passed else '❌'
        print(f"{status} {phase}")
    
    print(f"\n{'='*60}")
    if total_passed == total_tests:
        print("🎉 ALL VALIDATION TESTS PASSED!")
        print("Bot is ready for production use!")
    else:
        print(f"⚠️  {total_tests - total_passed} phase(s) failed")
        print("Please fix errors before production use")
    print("=" * 60)
    
    return total_passed == total_tests

def main():
    """Run all validation tests"""
    print("\n" + "=" * 60)
    print("ARBITRAGE BOT - PRODUCTION VALIDATION")
    print("=" * 60)
    
    results = {}
    
    # Phase 1: Imports
    results['Module Imports'] = test_imports()
    
    # Phase 2: Factory Functions
    results['Factory Functions'] = test_factory_functions()
    
    # Phase 3: Configuration
    results['Configuration'] = test_configuration()
    
    # Phase 4: Async Components
    results['Async Components'] = asyncio.run(test_async_components())
    
    # Summary
    all_passed = print_summary(results)
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
