#!/usr/bin/env python3
"""
Comprehensive Final Test Suite
Tests all features of the integrated arbitrage bot before laptop deployment.
"""
import asyncio
import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("test_final")


async def main():
    """Run comprehensive test suite."""
    print("="*80)
    print("🧪 COMPREHENSIVE FINAL TEST SUITE")
    print("="*80)
    print()
    
    test_results = {
        'passed': 0,
        'failed': 0,
        'warnings': 0
    }
    
    # Test 1: Core Module Imports
    print("📦 Test 1: Core Module Imports...")
    try:
        from core.price_store import PriceStore
        from core.arbitrage import ArbitrageEngine
        from core.order_executor import OrderExecutor
        from core.balance_manager import get_balance_manager
        from core.risk_manager import get_risk_manager
        from core.state_manager import get_state_manager
        from core.telegram_bot import get_telegram_bot
        from core.resource_monitor import get_resource_monitor
        from core.triangular_arb import get_triangular_engine
        from core.order_type_selector import get_order_type_selector
        from core.strategy_manager import get_strategy_manager
        from core.rebalancer import get_auto_rebalancer
        from core.startup_validator import get_startup_validator
        from core.windows_optimizer import setup_windows_optimizations
        from core.volume_weighted_analyzer import get_volume_weighted_analyzer
        from core.slippage_predictor import get_slippage_predictor
        
        print("   ✅ All 16 core modules imported successfully")
        test_results['passed'] += 1
    except Exception as e:
        print(f"   ❌ Core module import failed: {e}")
        test_results['failed'] += 1
        return test_results
    
    # Test 2: Exchange Module Imports
    print("\n📦 Test 2: Exchange Module Imports...")
    try:
        from exchanges.bybit_ws import BybitWS
        from exchanges.kucoin_ws import KucoinWS
        from exchanges.htx_ws import HtxWS
        from exchanges.mexc_ws import MexcWS
        from exchanges.rest_clients.bybit_client import BybitRESTClient
        from exchanges.rest_clients.kucoin_client import KuCoinRESTClient
        from exchanges.rest_clients.htx_client import HTXRESTClient
        from exchanges.rest_clients.mexc_client import MEXCRESTClient
        
        print("   ✅ All 8 exchange modules imported successfully")
        test_results['passed'] += 1
    except Exception as e:
        print(f"   ❌ Exchange module import failed: {e}")
        test_results['failed'] += 1
    
    # Test 3: Settings Configuration
    print("\n⚙️  Test 3: Settings Configuration...")
    try:
        import settings
        
        # Check key settings
        assert hasattr(settings, 'DRY_RUN')
        assert hasattr(settings, 'TRADING_SYMBOLS')
        assert hasattr(settings, 'MIN_NET_ROI_PCT')
        assert hasattr(settings, 'MAX_EXPOSURE_USDT')
        
        print(f"   ✅ Settings loaded")
        print(f"      - DRY_RUN: {settings.DRY_RUN}")
        print(f"      - Trading Symbols: {len(settings.TRADING_SYMBOLS)}")
        print(f"      - MIN_NET_ROI: {settings.MIN_NET_ROI_PCT}%")
        print(f"      - MAX_EXPOSURE: ${settings.MAX_EXPOSURE_USDT}")
        
        if not settings.DRY_RUN:
            print("   ⚠️  WARNING: DRY_RUN is False - bot will trade with real money!")
            test_results['warnings'] += 1
        
        test_results['passed'] += 1
    except Exception as e:
        print(f"   ❌ Settings configuration failed: {e}")
        test_results['failed'] += 1
    
    # Test 4: Component Initialization
    print("\n🔧 Test 4: Component Initialization...")
    try:
        # Initialize all managers
        balance_manager = get_balance_manager()
        risk_manager = get_risk_manager()
        state_manager = get_state_manager()
        telegram_bot = get_telegram_bot(token="test_token", chat_id="test_chat")  # Mock
        resource_monitor = get_resource_monitor()
        triangular_engine = get_triangular_engine(
            exchanges=['Bybit', 'KuCoin', 'HTX', 'MEXC'],
            price_store=None,  # Mock
            executor=None  # Mock
        )
        order_selector = get_order_type_selector()
        strategy_manager = get_strategy_manager()
        rebalancer = get_auto_rebalancer(
            balance_manager=balance_manager,
            rest_clients={},
            telegram_bot=telegram_bot
        )
        startup_validator = get_startup_validator(
            rest_clients={},
            balance_manager=balance_manager,
            risk_manager=risk_manager,
            state_manager=state_manager,
            telegram_bot=telegram_bot
        )
        volume_analyzer = get_volume_weighted_analyzer()
        slippage_predictor = get_slippage_predictor()
        
        print("   ✅ All 11 managers/engines initialized successfully")
        test_results['passed'] += 1
    except Exception as e:
        print(f"   ❌ Component initialization failed: {e}")
        test_results['failed'] += 1
        # Set defaults to prevent cascading failures
        volume_analyzer = None
        slippage_predictor = None
        risk_manager = None
        balance_manager = None
        strategy_manager = None
        state_manager = None
    
    # Test 5: Volume-Weighted Analyzer
    print("\n📊 Test 5: Volume-Weighted Analyzer...")
    if not volume_analyzer:
        print("   ⚠️  Skipped (component not initialized)")
        test_results['warnings'] += 1
    else:
        try:
        # Mock orderbook
        buy_orderbook = {
            'asks': [
                (100.0, 1.0),
                (100.1, 2.0),
                (100.2, 3.0),
                (100.3, 1.5),
                (100.4, 2.5),
            ]
        }
        sell_orderbook = {
            'bids': [
                (101.0, 1.0),
                (100.9, 2.0),
                (100.8, 3.0),
                (100.7, 1.5),
                (100.6, 2.5),
            ]
        }
        
        result = volume_analyzer.analyze_opportunity(
            symbol='BTC/USDT',
            buy_exchange='Bybit',
            sell_exchange='KuCoin',
            buy_orderbook=buy_orderbook,
            sell_orderbook=sell_orderbook,
            target_quantity=2.0
        )
        
        if result:
            print(f"   ✅ Volume-weighted analysis successful")
            print(f"      - VWAP Buy: ${result.vwap_buy:.2f}")
            print(f"      - VWAP Sell: ${result.vwap_sell:.2f}")
            print(f"      - Spread: {result.spread_pct:.4f}%")
            print(f"      - Confidence: {result.confidence:.2f}")
            test_results['passed'] += 1
        else:
            print("   ⚠️  No result (insufficient depth)")
            test_results['warnings'] += 1
    except Exception as e:
        print(f"   ❌ Volume-weighted analyzer failed: {e}")
        test_results['failed'] += 1
    
    # Test 6: Slippage Predictor
    print("\n📊 Test 6: Slippage Predictor...")
    try:
        orderbook = {
            'asks': [
                (100.0, 0.5),
                (100.1, 1.0),
                (100.2, 1.5),
            ]
        }
        
        prediction = slippage_predictor.predict(
            symbol='BTC/USDT',
            exchange='Bybit',
            side='buy',
            quantity=1.0,
            orderbook=orderbook
        )
        
        print(f"   ✅ Slippage prediction successful")
        print(f"      - Predicted Slippage: {prediction.predicted_slippage_pct:.3f}%")
        print(f"      - Confidence: {prediction.confidence:.2f}")
        print(f"      - Depth Score: {prediction.orderbook_depth_score:.2f}")
        
        if prediction.recommended_quantity:
            print(f"      - Recommended Qty: {prediction.recommended_quantity:.6f} (adjusted)")
        
        test_results['passed'] += 1
    except Exception as e:
        print(f"   ❌ Slippage predictor failed: {e}")
        test_results['failed'] += 1
    
    # Test 7: Risk Manager
    print("\n🛡️  Test 7: Risk Manager...")
    try:
        # Test risk limits
        can_trade, reason = risk_manager.check_can_trade({
            'symbol': 'BTC/USDT',
            'buy_exchange': 'Bybit',
            'sell_exchange': 'KuCoin',
            'quantity': 0.01,
            'net_profit': 5.0,
            'gross_spread_pct': 0.5
        })
        
        print(f"   ✅ Risk manager operational")
        print(f"      - Can Trade: {can_trade}")
        if not can_trade:
            print(f"      - Reason: {reason}")
        
        # Get statistics
        stats = risk_manager.get_statistics()
        print(f"      - Daily P&L: ${stats.get('daily_pnl', 0):.2f}")
        print(f"      - Daily Trades: {stats.get('daily_trades', 0)}")
        
        test_results['passed'] += 1
    except Exception as e:
        print(f"   ❌ Risk manager failed: {e}")
        test_results['failed'] += 1
    
    # Test 8: Balance Manager
    print("\n💰 Test 8: Balance Manager...")
    try:
        # Test balance operations
        balance_manager.update_balance('Bybit', 'USDT', 1000.0)
        balance_manager.update_balance('KuCoin', 'USDT', 1000.0)
        balance_manager.update_balance('HTX', 'USDT', 1000.0)
        balance_manager.update_balance('MEXC', 'USDT', 1000.0)
        
        can_trade, reason = balance_manager.has_sufficient_balance(
            'Bybit', 'USDT', 50.0
        )
        
        print(f"   ✅ Balance manager operational")
        print(f"      - Can Trade: {can_trade}")
        print(f"      - Total Balance: ${balance_manager.get_total_balance('USDT'):.2f}")
        
        test_results['passed'] += 1
    except Exception as e:
        print(f"   ❌ Balance manager failed: {e}")
        test_results['failed'] += 1
    
    # Test 9: Strategy Manager
    print("\n🎯 Test 9: Strategy Manager...")
    try:
        # Record sample trades
        strategy_manager.record_trade(
            strategy='cross_exchange',
            profit=5.0,
            execution_time=0.5
        )
        
        stats = strategy_manager.get_statistics()
        print(f"   ✅ Strategy manager operational")
        print(f"      - Total Trades: {stats.get('total_trades', 0)}")
        
        test_results['passed'] += 1
    except Exception as e:
        print(f"   ❌ Strategy manager failed: {e}")
        test_results['failed'] += 1
    
    # Test 10: State Manager
    print("\n💾 Test 10: State Manager...")
    try:
        # Load state
        await state_manager.load_state()
        
        # Save state
        await state_manager.save_state()
        
        print(f"   ✅ State manager operational")
        print(f"      - State file: bot_state.json")
        
        test_results['passed'] += 1
    except Exception as e:
        print(f"   ❌ State manager failed: {e}")
        test_results['failed'] += 1
    
    # Test 11: Main Integrated Bot Import
    print("\n🤖 Test 11: Main Integrated Bot...")
    try:
        from main_integrated import IntegratedArbitrageBot
        
        bot = IntegratedArbitrageBot()
        
        print(f"   ✅ Main integrated bot imported successfully")
        print(f"      - Bot instance created")
        print(f"      - Ready for initialization")
        
        test_results['passed'] += 1
    except Exception as e:
        print(f"   ❌ Main integrated bot import failed: {e}")
        test_results['failed'] += 1
    
    # Final Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    print(f"✅ Passed:   {test_results['passed']}/11")
    print(f"❌ Failed:   {test_results['failed']}/11")
    print(f"⚠️  Warnings: {test_results['warnings']}")
    print()
    
    if test_results['failed'] == 0:
        print("🎉 ALL TESTS PASSED! Bot is ready for deployment!")
        print()
        print("Next steps:")
        print("1. Configure API keys in .env file")
        print("2. Verify DRY_RUN=true for safe testing")
        print("3. Run: python main_integrated.py")
        print("4. Monitor via Telegram notifications")
        print("5. Check logs in arbitrage_bot.log")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED! Please fix issues before deployment.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
