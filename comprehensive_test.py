#!/usr/bin/env python3
"""
Comprehensive Integration Test for Arbitrage Bot
Tests the complete bot workflow without external dependencies
"""
import sys
import asyncio
import time
from pathlib import Path

print("=" * 70)
print("COMPREHENSIVE ARBITRAGE BOT INTEGRATION TEST")
print("=" * 70)

def test_phase1_imports():
    """Phase 1: Test all imports"""
    print("\n📦 PHASE 1: Module Imports")
    print("-" * 70)
    
    errors = []
    
    # Import settings first
    try:
        import settings
        print(f"✅ settings")
    except Exception as e:
        print(f"❌ settings: {e}")
        errors.append(('settings', e))
        return False, errors
    
    # Core modules
    core_modules = [
        'price_store', 'arbitrage', 'order_executor', 'exchange_config',
        'balance_manager', 'risk_manager', 'state_manager',
        'triangular_arb', 'order_type_selector', 'strategy_manager',
        'rebalancer', 'startup_validator', 'windows_optimizer',
        'volume_weighted_analyzer', 'slippage_predictor'
    ]
    
    for module in core_modules:
        try:
            exec(f"from core import {module}")
            print(f"✅ core.{module}")
        except Exception as e:
            print(f"❌ core.{module}: {e}")
            errors.append((f'core.{module}', e))
    
    return len(errors) == 0, errors

def test_phase2_initialization():
    """Phase 2: Test component initialization"""
    print("\n🏗️  PHASE 2: Component Initialization")
    print("-" * 70)
    
    errors = []
    
    # Initialize PriceStore
    try:
        from core.price_store import PriceStore
        store = PriceStore()
        print("✅ PriceStore created")
    except Exception as e:
        print(f"❌ PriceStore: {e}")
        errors.append(('PriceStore', e))
        return False, errors
    
    # Initialize OrderExecutor
    try:
        from core.order_executor import OrderExecutor
        executor = OrderExecutor(dry_run=True)
        print("✅ OrderExecutor created (DRY_RUN mode)")
    except Exception as e:
        print(f"❌ OrderExecutor: {e}")
        errors.append(('OrderExecutor', e))
        return False, errors
    
    # Initialize ArbitrageEngine
    try:
        from core.arbitrage import ArbitrageEngine
        engine = ArbitrageEngine(
            store,
            default_qty=0.001,
            min_net_pct=0.03,
            executor=executor
        )
        print("✅ ArbitrageEngine created")
    except Exception as e:
        print(f"❌ ArbitrageEngine: {e}")
        errors.append(('ArbitrageEngine', e))
        return False, errors
    
    # Initialize managers
    try:
        from core.balance_manager import get_balance_manager
        balance_mgr = get_balance_manager()
        print("✅ BalanceManager created")
    except Exception as e:
        print(f"⚠️  BalanceManager: {e}")
        # Not critical for test
    
    try:
        from core.risk_manager import get_risk_manager
        risk_mgr = get_risk_manager()
        print("✅ RiskManager created")
    except Exception as e:
        print(f"❌ RiskManager: {e}")
        errors.append(('RiskManager', e))
    
    try:
        from core.state_manager import get_state_manager
        state_mgr = get_state_manager()
        print("✅ StateManager created")
    except Exception as e:
        print(f"❌ StateManager: {e}")
        errors.append(('StateManager', e))
    
    try:
        from core.strategy_manager import get_strategy_manager
        strategy_mgr = get_strategy_manager()
        print("✅ StrategyManager created")
    except Exception as e:
        print(f"❌ StrategyManager: {e}")
        errors.append(('StrategyManager', e))
    
    return len(errors) == 0, errors

async def test_phase3_async_operations():
    """Phase 3: Test async operations"""
    print("\n⚡ PHASE 3: Async Operations")
    print("-" * 70)
    
    errors = []
    
    # Test PriceStore update
    try:
        from core.price_store import PriceStore
        store = PriceStore()
        
        # Simulate orderbook update using correct signature
        test_symbol = "BTC/USDT"
        test_exchange = "Bybit"
        
        # Use update_levels for orderbook data
        await store.update_levels(
            test_exchange,
            test_symbol,
            bids_levels=[[50000.0, 1.0], [49999.0, 2.0]],
            asks_levels=[[50001.0, 1.0], [50002.0, 2.0]]
        )
        
        snapshot = await store.get(test_symbol)
        
        if test_exchange in snapshot:
            print(f"✅ PriceStore update/snapshot working")
        else:
            raise Exception("PriceStore update failed")
            
    except Exception as e:
        print(f"❌ PriceStore async: {e}")
        errors.append(('PriceStore async', e))
    
    # Test arbitrage detection (dry run)
    try:
        from core.arbitrage import ArbitrageEngine
        from core.order_executor import OrderExecutor
        
        store = PriceStore()
        executor = OrderExecutor(dry_run=True)
        engine = ArbitrageEngine(store, executor=executor)
        
        # Add test data using update_levels
        await store.update_levels("Bybit", "BTC/USDT",
            bids_levels=[[50000.0, 1.0]], asks_levels=[[50100.0, 1.0]]
        )
        await store.update_levels("KuCoin", "BTC/USDT",
            bids_levels=[[50200.0, 1.0]], asks_levels=[[50300.0, 1.0]]
        )
        
        # Try scanning (should detect potential arb)
        opportunities = await engine.scan_once("BTC/USDT")
        print(f"✅ ArbitrageEngine scan working ({len(opportunities)} opportunities)")
        
    except Exception as e:
        print(f"❌ ArbitrageEngine async: {e}")
        errors.append(('ArbitrageEngine async', e))
    
    return len(errors) == 0, errors

def test_phase4_configuration():
    """Phase 4: Test configuration"""
    print("\n⚙️  PHASE 4: Configuration")
    print("-" * 70)
    
    errors = []
    
    try:
        import settings
        
        config = settings.get_config()
        print(f"✅ Configuration loaded")
        print(f"   - DRY_RUN: {config['DRY_RUN']}")
        print(f"   - MIN_NET_ROI_PCT: {config['MIN_NET_ROI_PCT']}%")
        print(f"   - MAX_EXPOSURE: ${config['MAX_EXPOSURE_USDT']}")
        print(f"   - Symbols: {len(config['TRADING_SYMBOLS'])} pairs")
        print(f"   - Exchanges: {', '.join(config['EXCHANGES'])}")
        
        if not config['DRY_RUN']:
            print("⚠️  WARNING: DRY_RUN is disabled!")
        
    except Exception as e:
        print(f"❌ Configuration: {e}")
        errors.append(('Configuration', e))
    
    return len(errors) == 0, errors

def test_phase5_integration():
    """Phase 5: Test integrated workflow"""
    print("\n🔄 PHASE 5: Integrated Workflow")
    print("-" * 70)
    
    errors = []
    
    try:
        # Simulate a mini bot run
        from core.price_store import PriceStore
        from core.arbitrage import ArbitrageEngine
        from core.order_executor import OrderExecutor
        from core.risk_manager import get_risk_manager
        from core.strategy_manager import get_strategy_manager
        
        # Create components
        store = PriceStore()
        executor = OrderExecutor(dry_run=True)
        risk_mgr = get_risk_manager()
        strategy_mgr = get_strategy_manager()
        
        engine = ArbitrageEngine(
            store,
            executor=executor,
            risk_manager=risk_mgr,
            strategy_manager=strategy_mgr
        )
        
        print("✅ All components integrated")
        
        # Simulate market data using async
        async def setup_market_data():
            for exchange in ['Bybit', 'KuCoin', 'HTX', 'MEXC']:
                await store.update_levels(
                    exchange, "BTC/USDT",
                    bids_levels=[[50000.0 + (hash(exchange) % 100), 1.0]],
                    asks_levels=[[50100.0 + (hash(exchange) % 100), 1.0]]
                )
        
        # Run async setup
        import asyncio
        asyncio.run(setup_market_data())
        
        print("✅ Market data simulated")
        
        # Scan for opportunities (async call)
        async def scan_test():
            opportunities = await engine.scan_once("BTC/USDT")
            return opportunities
        
        opportunities = asyncio.run(scan_test())
        print(f"✅ Scan completed ({len(opportunities)} opportunities found)")
        
        # Test risk check
        if opportunities:
            opp = opportunities[0]
            can_trade, reason = risk_mgr.check_can_trade(opp)
            print(f"✅ Risk check performed: {can_trade}")
        
        print("✅ Integrated workflow successful")
        
    except Exception as e:
        print(f"❌ Integration: {e}")
        errors.append(('Integration', e))
        import traceback
        traceback.print_exc()
    
    return len(errors) == 0, errors

def print_summary(results):
    """Print test summary"""
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    total_passed = sum(1 for passed, _ in results.values() if passed)
    total_phases = len(results)
    
    for phase, (passed, errors) in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {phase}")
        if errors:
            for error_name, error_msg in errors:
                print(f"       └─ {error_name}: {str(error_msg)[:60]}")
    
    print("\n" + "=" * 70)
    if total_passed == total_phases:
        print("🎉 ALL TESTS PASSED!")
        print("Bot is working correctly like Swiss clockwork! 🕐")
        return 0
    else:
        print(f"⚠️  {total_phases - total_passed} phase(s) failed")
        print("Please review errors above")
        return 1

def main():
    """Run all tests"""
    print("\nTesting bot integration without external dependencies...")
    print("This validates core functionality is working correctly.\n")
    
    results = {}
    
    # Phase 1: Imports
    passed, errors = test_phase1_imports()
    results['Phase 1: Module Imports'] = (passed, errors)
    
    if not passed:
        print("\n❌ Critical imports failed, cannot continue")
        return print_summary(results)
    
    # Phase 2: Initialization
    passed, errors = test_phase2_initialization()
    results['Phase 2: Component Initialization'] = (passed, errors)
    
    # Phase 3: Async Operations
    passed, errors = asyncio.run(test_phase3_async_operations())
    results['Phase 3: Async Operations'] = (passed, errors)
    
    # Phase 4: Configuration
    passed, errors = test_phase4_configuration()
    results['Phase 4: Configuration'] = (passed, errors)
    
    # Phase 5: Integration
    passed, errors = test_phase5_integration()
    results['Phase 5: Integrated Workflow'] = (passed, errors)
    
    # Print summary
    return print_summary(results)

if __name__ == '__main__':
    sys.exit(main())
