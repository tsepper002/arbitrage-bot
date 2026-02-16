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
    
    print("[OK] Configuration tests passed")


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
    print(f"[OK] Dry run execution: {result['status']}")
    
    # Test statistics
    stats = executor.get_statistics()
    assert stats['total_orders'] == 1, "Should have 1 simulated order"
    assert stats['mode'] == 'dry_run', "Should be in dry_run mode"
    print(f"[OK] Statistics: {stats}")
    
    print("\n[OK] Order executor dry run tests passed")


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
    print(f"[OK] Cooldown working: {result['reason']}")
    
    # Test different symbol (should work)
    opportunity2 = opportunity.copy()
    opportunity2['symbol'] = 'ETH-USDT'
    result = executor.execute_arbitrage(opportunity2)
    assert result['status'] == 'simulated', "Different symbol should work"
    print(f"[OK] Different symbol executed: {result['status']}")
    
    print("\n[OK] Rate limiting tests passed")


def test_health_monitoring():
    """Test WebSocket health monitoring helpers."""
    print("\n" + "="*60)
    print("TEST 4: Health Monitoring")
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
    print(f"[OK] Health status: {health}")
    
    # Test reconnect helper
    reconnect = WSReconnectHelper("TestExchange")
    should_reconnect, reason = reconnect.should_reconnect()
    assert should_reconnect == True, "Should allow reconnect"
    
    reconnect.on_successful_connection()
    delay = reconnect.get_next_delay()
    assert delay == settings.WS_RECONNECT_DELAY_SEC, "Should use initial delay"
    print(f"[OK] Reconnect delay: {delay}s")
    
    print("\n[OK] Health monitoring tests passed")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print(" Arbitrage Bot - Core Functionality Tests")
    print("="*70)
    
    try:
        test_configuration()
        test_order_executor_dry_run()
        test_rate_limiting()
        test_health_monitoring()
        
        print("\n" + "="*70)
        print(" [OK] ALL TESTS PASSED")
        print("="*70)
        print("\nThe arbitrage bot core functionality is working correctly!")
        print("Network connectivity to exchanges is required for live operation.")
        print("\n")
        
        return 0
        
    except AssertionError as e:
        print(f"\n[FAILED] TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
