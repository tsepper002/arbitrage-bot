#!/usr/bin/env python3
"""
Test script to validate core functionality without external connections.
Tests configuration, order executor, and risk management features.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import settings
from core.order_executor import OrderExecutor


def test_configuration():
    """Test that configuration is properly loaded."""
    print("\n" + "="*60)
    print("TEST 1: Configuration")
    print("="*60)
    
    print(settings.get_config_summary())
    
    assert settings.DRY_RUN is True, "DRY_RUN should default to True"
    assert settings.MIN_NET_ROI_PCT > 0, "MIN_NET_ROI_PCT should be positive"
    assert settings.MAX_EXPOSURE_USDT > 0, "MAX_EXPOSURE_USDT should be positive"
    assert settings.SAFETY_FACTOR > 0 and settings.SAFETY_FACTOR <= 1, "SAFETY_FACTOR should be between 0 and 1"
    
    print("✅ Configuration tests passed")


def test_order_executor_dry_run():
    """Test order executor in dry run mode."""
    print("\n" + "="*60)
    print("TEST 2: Order Executor (Dry Run)")
    print("="*60)
    
    executor = OrderExecutor(dry_run=True)
    
    # Create test opportunity
    opportunity = {
        'symbol': 'BTC-USDT',
        'buy_ex': 'KuCoin',
        'sell_ex': 'Bybit',
        'qty': 0.001,
        'buy_avg': 45000.0,
        'sell_avg': 45050.0,
        'net': 0.0234,
        'roi_pct': 0.052
    }
    
    # Test execution
    result = executor.execute_arbitrage(opportunity)
    assert result['status'] == 'simulated', "Should simulate in dry run mode"
    print(f"✅ Dry run execution: {result['status']}")
    
    # Test statistics
    stats = executor.get_statistics()
    assert stats['total_orders'] == 1, "Should have 1 simulated order"
    assert stats['mode'] == 'dry_run', "Should be in dry_run mode"
    print(f"✅ Statistics: {stats}")
    
    print("\n✅ Order executor dry run tests passed")


def test_rate_limiting():
    """Test rate limiting and cooldown features."""
    print("\n" + "="*60)
    print("TEST 3: Rate Limiting & Cooldowns")
    print("="*60)
    
    executor = OrderExecutor(dry_run=True)
    
    opportunity = {
        'symbol': 'BTC-USDT',
        'buy_ex': 'KuCoin',
        'sell_ex': 'Bybit',
        'qty': 0.001,
        'buy_avg': 45000.0,
        'sell_avg': 45050.0,
        'net': 0.0234,
        'roi_pct': 0.052
    }
    
    # Execute multiple times
    for i in range(3):
        result = executor.execute_arbitrage(opportunity)
        print(f"  Trade {i+1}: {result['status']}")
    
    # Should be blocked by cooldown
    result = executor.execute_arbitrage(opportunity)
    assert result['status'] == 'blocked', "Should be blocked by cooldown"
    print(f"✅ Cooldown working: {result['reason']}")
    
    # Test different symbol (should work)
    opportunity2 = opportunity.copy()
    opportunity2['symbol'] = 'ETH-USDT'
    result = executor.execute_arbitrage(opportunity2)
    assert result['status'] == 'simulated', "Different symbol should work"
    print(f"✅ Different symbol executed: {result['status']}")
    
    print("\n✅ Rate limiting tests passed")


def test_virtual_capital():
    """Test virtual capital tracking in dry run mode."""
    print("\n" + "="*60)
    print("TEST 4: Virtual Capital Tracking")
    print("="*60)

    executor = OrderExecutor(dry_run=True)

    # Should start with default virtual capital
    assert executor.virtual_balance_usdt == settings.VIRTUAL_CAPITAL_USDT, "Should start with configured virtual capital"
    assert executor.initial_virtual_balance == settings.VIRTUAL_CAPITAL_USDT, "Initial balance should match"
    print(f"✅ Starting virtual balance: ${executor.virtual_balance_usdt:.2f}")

    # Execute a profitable trade
    opp = {
        'symbol': 'ETH-USDT',
        'buy_ex': 'Bybit',
        'sell_ex': 'MEXC',
        'qty': 0.1,
        'buy_avg': 3000.0,
        'sell_avg': 3010.0,
        'net': 0.82,
        'roi_pct': 0.273
    }
    result = executor.execute_arbitrage(opp)
    assert result['status'] == 'simulated', "Should simulate trade"

    # Virtual balance should increase by (sell_proceeds - buy_cost)
    expected_balance = settings.VIRTUAL_CAPITAL_USDT - (0.1 * 3000.0) + (0.1 * 3010.0)
    assert abs(executor.virtual_balance_usdt - expected_balance) < 0.01, \
        f"Virtual balance should be ~${expected_balance:.2f}, got ${executor.virtual_balance_usdt:.2f}"
    print(f"✅ Virtual balance after trade: ${executor.virtual_balance_usdt:.2f}")

    # Stats should show virtual P&L
    stats = executor.get_statistics()
    assert 'virtual_balance' in stats, "Stats should include virtual_balance"
    assert 'virtual_pnl' in stats, "Stats should include virtual_pnl"
    assert stats['virtual_pnl'] > 0, "P&L should be positive after profitable trade"
    print(f"✅ Virtual P&L: ${stats['virtual_pnl']:.4f}")

    # Test insufficient capital blocking
    executor2 = OrderExecutor(dry_run=True)
    big_opp = {
        'symbol': 'BTC-USDT',
        'buy_ex': 'KuCoin',
        'sell_ex': 'Bybit',
        'qty': 1.0,
        'buy_avg': 100000.0,
        'sell_avg': 100100.0,
        'net': 40.0,
        'roi_pct': 0.04
    }
    result = executor2.execute_arbitrage(big_opp)
    assert result['status'] == 'blocked', "Should block trade exceeding virtual capital"
    assert 'virtual capital' in result['reason'].lower(), "Reason should mention virtual capital"
    print(f"✅ Insufficient capital blocked: {result['reason']}")

    print("\n✅ Virtual capital tests passed")


def test_mexc_config():
    """Test that MEXC is properly configured."""
    print("\n" + "="*60)
    print("TEST 5: MEXC Exchange Config")
    print("="*60)

    from core.exchange_config import EXCHANGE_PARAMS

    assert 'MEXC' in EXCHANGE_PARAMS, "MEXC should be in EXCHANGE_PARAMS"
    mexc_params = EXCHANGE_PARAMS['MEXC']
    assert 'maker' in mexc_params, "MEXC should have maker fee"
    assert 'taker' in mexc_params, "MEXC should have taker fee"
    assert mexc_params['taker'] > 0, "MEXC taker fee should be positive"
    print(f"✅ MEXC config: maker={mexc_params['maker']}, taker={mexc_params['taker']}")

    # Test MEXC class has stop method
    from exchanges.mexc import MEXC
    mexc = MEXC(None, [])
    assert hasattr(mexc, 'stop'), "MEXC should have stop method"
    assert hasattr(mexc, 'run'), "MEXC should have run method"
    print("✅ MEXC class has required methods")

    print("\n✅ MEXC config tests passed")


def test_bybit_rest():
    """Test BybitREST v5 API client."""
    print("\n" + "="*60)
    print("TEST 6: Bybit REST v5 Client")
    print("="*60)

    from exchanges.bybit_rest import BybitREST

    # Test instantiation without credentials
    rest = BybitREST()
    assert rest.base_url == "https://api.bybit.com", "Should use correct base URL"
    assert hasattr(rest, 'get_balance'), "Should have get_balance method"
    assert hasattr(rest, '_generate_signature'), "Should have signature generation"
    print("✅ BybitREST instantiation OK")

    # Test signature generation with test credentials
    rest_auth = BybitREST(api_key="test_key", api_secret="test_secret")
    sig = rest_auth._generate_signature("1234567890", "accountType=UNIFIED")
    assert isinstance(sig, str), "Signature should be a string"
    assert len(sig) == 64, "HMAC-SHA256 hex digest should be 64 chars"
    print(f"✅ Signature generation works: {sig[:16]}...")

    # Test auth headers
    headers = rest_auth._auth_headers("accountType=UNIFIED")
    assert "X-BAPI-API-KEY" in headers, "Should include API key header"
    assert "X-BAPI-TIMESTAMP" in headers, "Should include timestamp header"
    assert "X-BAPI-SIGN" in headers, "Should include signature header"
    assert "X-BAPI-RECV-WINDOW" in headers, "Should include recv window header"
    print("✅ Auth headers generated correctly")

    # Test that empty credentials raise error
    try:
        rest._auth_headers("test")
        assert False, "Should raise ValueError for empty credentials"
    except ValueError as e:
        print(f"✅ Empty credentials rejected: {e}")

    print("\n✅ Bybit REST tests passed")


def test_telegram_notifier():
    """Test Telegram notifier initialization."""
    print("\n" + "="*60)
    print("TEST 7: Telegram Notifier")
    print("="*60)

    from utils.telegram import TelegramNotifier

    # Should be disabled by default (no token/chat_id)
    notifier = TelegramNotifier()
    assert notifier.enabled is False, "Should be disabled without credentials"
    print("✅ Telegram disabled by default")

    # Should be disabled even with token but no TELEGRAM_ENABLED
    notifier2 = TelegramNotifier(token="fake_token", chat_id="fake_chat")
    assert notifier2.enabled is False, "Should be disabled when TELEGRAM_ENABLED is False"
    print("✅ Telegram disabled when TELEGRAM_ENABLED is False")

    print("\n✅ Telegram notifier tests passed")


def test_health_monitoring():
    """Test WebSocket health monitoring helpers."""
    print("\n" + "="*60)
    print("TEST 8: Health Monitoring")
    print("="*60)
    
    from exchanges.ws_helpers import WSHealthMonitor, WSReconnectHelper
    
    # Test health monitor
    monitor = WSHealthMonitor("TestExchange")
    monitor.on_connection_start()
    monitor.on_message_received("BTC-USDT")
    monitor.on_message_received("ETH-USDT")
    
    health = monitor.check_health()
    assert health['connected'] == True, "Should be connected"
    assert health['tracked_symbols'] == 2, "Should track 2 symbols"
    assert health['is_healthy'] == True, "Should be healthy"
    print(f"✅ Health status: {health}")
    
    # Test reconnect helper
    reconnect = WSReconnectHelper("TestExchange")
    should_reconnect, reason = reconnect.should_reconnect()
    assert should_reconnect == True, "Should allow reconnect"
    
    reconnect.on_successful_connection()
    delay = reconnect.get_next_delay()
    assert delay == settings.WS_RECONNECT_DELAY_SEC, "Should use initial delay"
    print(f"✅ Reconnect delay: {delay}s")
    
    print("\n✅ Health monitoring tests passed")


def test_cli_arguments():
    """Test command-line argument parsing."""
    print("\n" + "="*60)
    print("TEST 9: CLI Argument Parsing")
    print("="*60)

    from main import parse_args, apply_cli_overrides

    # --mode dry-run sets DRY_RUN=True
    args = parse_args(["--mode", "dry-run"])
    assert args.mode == "dry-run"
    saved = settings.DRY_RUN
    apply_cli_overrides(args)
    assert settings.DRY_RUN is True, "dry-run should set DRY_RUN=True"
    print("✅ --mode dry-run works")

    # --mode live sets DRY_RUN=False
    args = parse_args(["--mode", "live"])
    apply_cli_overrides(args)
    assert settings.DRY_RUN is False, "live should set DRY_RUN=False"
    print("✅ --mode live works")

    # no --mode keeps existing value
    settings.DRY_RUN = True
    args = parse_args([])
    apply_cli_overrides(args)
    assert settings.DRY_RUN is True, "no --mode should keep default"
    print("✅ no --mode keeps default")

    # --symbols override
    args = parse_args(["--symbols", "BTC-USDT,ETH-USDT"])
    apply_cli_overrides(args)
    assert settings.TRADING_SYMBOLS == ["BTC-USDT", "ETH-USDT"]
    print("✅ --symbols override works")

    # Restore defaults
    settings.DRY_RUN = saved
    import importlib
    importlib.reload(settings)
    settings.DRY_RUN = saved

    print("\n✅ CLI argument tests passed")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print(" Arbitrage Bot - Core Functionality Tests")
    print("="*70)
    
    try:
        test_configuration()
        test_order_executor_dry_run()
        test_rate_limiting()
        test_virtual_capital()
        test_mexc_config()
        test_bybit_rest()
        test_telegram_notifier()
        test_health_monitoring()
        test_cli_arguments()
        
        print("\n" + "="*70)
        print(" ✅ ALL TESTS PASSED")
        print("="*70)
        print("\nThe arbitrage bot core functionality is working correctly!")
        print("Network connectivity to exchanges is required for live operation.")
        print("\n")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
