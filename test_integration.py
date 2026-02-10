#!/usr/bin/env python3
"""
test_integration.py — Comprehensive test suite for the integrated arbitrage bot
Tests all components individually and together to ensure proper integration.
"""
import sys
import os
import asyncio
import logging
from typing import Dict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import settings

# Configure logging for testing
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("integration_test")


class IntegrationTester:
    """Comprehensive integration testing suite."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def test(self, name: str, condition: bool, message: str = ""):
        """Run a single test and report results."""
        if condition:
            print(f"✅ PASS: {name}")
            if message:
                print(f"   {message}")
            self.passed += 1
            return True
        else:
            print(f"❌ FAIL: {name}")
            if message:
                print(f"   {message}")
            self.failed += 1
            return False
    
    def warn(self, name: str, message: str):
        """Report a warning."""
        print(f"⚠️  WARN: {name}")
        print(f"   {message}")
        self.warnings += 1
    
    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"✅ Passed: {self.passed}/{total}")
        print(f"❌ Failed: {self.failed}/{total}")
        print(f"⚠️  Warnings: {self.warnings}")
        print("="*80)
        
        if self.failed == 0:
            print("🎉 ALL TESTS PASSED!")
            return 0
        else:
            print("❌ SOME TESTS FAILED!")
            return 1


async def test_imports():
    """Test that all modules can be imported."""
    tester = IntegrationTester()
    print("\n" + "="*80)
    print("TEST SUITE 1: Module Imports")
    print("="*80)
    
    # Core modules
    try:
        from core.price_store import PriceStore
        tester.test("Import core.price_store", True)
    except Exception as e:
        tester.test("Import core.price_store", False, str(e))
    
    try:
        from core.arbitrage import ArbitrageEngine
        tester.test("Import core.arbitrage", True)
    except Exception as e:
        tester.test("Import core.arbitrage", False, str(e))
    
    try:
        from core.order_executor import OrderExecutor
        tester.test("Import core.order_executor", True)
    except Exception as e:
        tester.test("Import core.order_executor", False, str(e))
    
    try:
        from core.balance_manager import get_balance_manager
        tester.test("Import core.balance_manager", True)
    except Exception as e:
        tester.test("Import core.balance_manager", False, str(e))
    
    try:
        from core.risk_manager import get_risk_manager
        tester.test("Import core.risk_manager", True)
    except Exception as e:
        tester.test("Import core.risk_manager", False, str(e))
    
    try:
        from core.state_manager import get_state_manager
        tester.test("Import core.state_manager", True)
    except Exception as e:
        tester.test("Import core.state_manager", False, str(e))
    
    try:
        from core.telegram_bot import get_telegram_bot
        tester.test("Import core.telegram_bot", True)
    except Exception as e:
        tester.test("Import core.telegram_bot", False, str(e))
    
    try:
        from core.resource_monitor import get_resource_monitor
        tester.test("Import core.resource_monitor", True)
    except Exception as e:
        tester.test("Import core.resource_monitor", False, str(e))
    
    try:
        from core.triangular_arb import get_triangular_engine
        tester.test("Import core.triangular_arb", True)
    except Exception as e:
        tester.test("Import core.triangular_arb", False, str(e))
    
    try:
        from core.order_type_selector import get_order_type_selector
        tester.test("Import core.order_type_selector", True)
    except Exception as e:
        tester.test("Import core.order_type_selector", False, str(e))
    
    try:
        from core.strategy_manager import get_strategy_manager
        tester.test("Import core.strategy_manager", True)
    except Exception as e:
        tester.test("Import core.strategy_manager", False, str(e))
    
    try:
        from core.rebalancer import get_auto_rebalancer
        tester.test("Import core.rebalancer", True)
    except Exception as e:
        tester.test("Import core.rebalancer", False, str(e))
    
    try:
        from core.startup_validator import get_startup_validator
        tester.test("Import core.startup_validator", True)
    except Exception as e:
        tester.test("Import core.startup_validator", False, str(e))
    
    try:
        from core.windows_optimizer import setup_windows_optimizations
        tester.test("Import core.windows_optimizer", True)
    except Exception as e:
        tester.test("Import core.windows_optimizer", False, str(e))
    
    # REST clients
    try:
        from exchanges.rest_clients.bybit_client import BybitRESTClient
        tester.test("Import bybit REST client", True)
    except Exception as e:
        tester.test("Import bybit REST client", False, str(e))
    
    try:
        from exchanges.rest_clients.kucoin_client import KuCoinRESTClient
        tester.test("Import kucoin REST client", True)
    except Exception as e:
        tester.test("Import kucoin REST client", False, str(e))
    
    try:
        from exchanges.rest_clients.htx_client import HTXRESTClient
        tester.test("Import htx REST client", True)
    except Exception as e:
        tester.test("Import htx REST client", False, str(e))
    
    try:
        from exchanges.rest_clients.mexc_client import MEXCRESTClient
        tester.test("Import mexc REST client", True)
    except Exception as e:
        tester.test("Import mexc REST client", False, str(e))
    
    # WebSocket clients
    try:
        from exchanges.bybit_ws import BybitWS
        tester.test("Import bybit WebSocket", True)
    except Exception as e:
        tester.test("Import bybit WebSocket", False, str(e))
    
    try:
        from exchanges.kucoin_ws import KucoinWS
        tester.test("Import kucoin WebSocket", True)
    except Exception as e:
        tester.test("Import kucoin WebSocket", False, str(e))
    
    try:
        from exchanges.htx_ws import HtxWS
        tester.test("Import htx WebSocket", True)
    except Exception as e:
        tester.test("Import htx WebSocket", False, str(e))
    
    try:
        from exchanges.mexc_ws import MexcWS
        tester.test("Import mexc WebSocket", True)
    except Exception as e:
        tester.test("Import mexc WebSocket", False, str(e))
    
    return tester


async def test_component_initialization():
    """Test that all components can be initialized."""
    tester = IntegrationTester()
    print("\n" + "="*80)
    print("TEST SUITE 2: Component Initialization")
    print("="*80)
    
    # Price Store
    try:
        from core.price_store import PriceStore
        store = PriceStore()
        tester.test("Initialize PriceStore", True)
    except Exception as e:
        tester.test("Initialize PriceStore", False, str(e))
        return tester
    
    # Balance Manager
    try:
        from core.balance_manager import get_balance_manager
        balance_mgr = get_balance_manager()
        tester.test("Initialize BalanceManager", True)
    except Exception as e:
        tester.test("Initialize BalanceManager", False, str(e))
    
    # Risk Manager
    try:
        from core.risk_manager import get_risk_manager
        risk_mgr = get_risk_manager()
        tester.test("Initialize RiskManager", True)
    except Exception as e:
        tester.test("Initialize RiskManager", False, str(e))
    
    # State Manager
    try:
        from core.state_manager import get_state_manager
        state_mgr = get_state_manager()
        tester.test("Initialize StateManager", True)
    except Exception as e:
        tester.test("Initialize StateManager", False, str(e))
    
    # Resource Monitor
    try:
        from core.resource_monitor import get_resource_monitor
        resource_mon = get_resource_monitor()
        tester.test("Initialize ResourceMonitor", True)
    except Exception as e:
        tester.test("Initialize ResourceMonitor", False, str(e))
    
    # Strategy Manager
    try:
        from core.strategy_manager import get_strategy_manager
        strategy_mgr = get_strategy_manager()
        tester.test("Initialize StrategyManager", True)
    except Exception as e:
        tester.test("Initialize StrategyManager", False, str(e))
    
    # Order Executor
    try:
        from core.order_executor import OrderExecutor
        executor = OrderExecutor(dry_run=True)
        tester.test("Initialize OrderExecutor", True)
    except Exception as e:
        tester.test("Initialize OrderExecutor", False, str(e))
    
    # Arbitrage Engine
    try:
        from core.arbitrage import ArbitrageEngine
        engine = ArbitrageEngine(store)
        tester.test("Initialize ArbitrageEngine", True)
    except Exception as e:
        tester.test("Initialize ArbitrageEngine", False, str(e))
    
    # Windows Optimizer
    try:
        from core.windows_optimizer import setup_windows_optimizations
        optimizer = setup_windows_optimizations()
        tester.test("Initialize WindowsOptimizer", True)
    except Exception as e:
        tester.test("Initialize WindowsOptimizer", False, str(e))
    
    return tester


async def test_configuration():
    """Test configuration settings."""
    tester = IntegrationTester()
    print("\n" + "="*80)
    print("TEST SUITE 3: Configuration")
    print("="*80)
    
    # Check critical settings
    tester.test("DRY_RUN is set", settings.DRY_RUN is not None)
    tester.test("MIN_NET_ROI_PCT is valid", 
                isinstance(settings.MIN_NET_ROI_PCT, (int, float)) and settings.MIN_NET_ROI_PCT > 0)
    tester.test("MAX_EXPOSURE_USDT is valid",
                isinstance(settings.MAX_EXPOSURE_USDT, (int, float)) and settings.MAX_EXPOSURE_USDT > 0)
    tester.test("TRADING_SYMBOLS is not empty", len(settings.TRADING_SYMBOLS) > 0)
    tester.test("SCAN_INTERVAL_SEC is valid",
                isinstance(settings.SCAN_INTERVAL_SEC, (int, float)) and settings.SCAN_INTERVAL_SEC > 0)
    
    # Check API key environment variables
    bybit_key = os.getenv("ARB_BYBIT_KEY", "")
    kucoin_key = os.getenv("ARB_KUCOIN_KEY", "")
    htx_key = os.getenv("ARB_HTX_KEY", "")
    mexc_key = os.getenv("ARB_MEXC_KEY", "")
    
    if not bybit_key:
        tester.warn("Bybit API key", "Not configured (live trading disabled)")
    else:
        tester.test("Bybit API key configured", True)
    
    if not kucoin_key:
        tester.warn("KuCoin API key", "Not configured (live trading disabled)")
    else:
        tester.test("KuCoin API key configured", True)
    
    if not htx_key:
        tester.warn("HTX API key", "Not configured (live trading disabled)")
    else:
        tester.test("HTX API key configured", True)
    
    if not mexc_key:
        tester.warn("MEXC API key", "Not configured (live trading disabled)")
    else:
        tester.test("MEXC API key configured", True)
    
    # Check Telegram configuration
    telegram_token = os.getenv("ARB_TELEGRAM_TOKEN", "")
    telegram_chat = os.getenv("ARB_TELEGRAM_CHAT_ID", "")
    
    if not telegram_token or not telegram_chat:
        tester.warn("Telegram", "Not configured (notifications disabled)")
    else:
        tester.test("Telegram configured", True)
    
    return tester


async def test_risk_manager():
    """Test risk manager functionality."""
    tester = IntegrationTester()
    print("\n" + "="*80)
    print("TEST SUITE 4: Risk Manager")
    print("="*80)
    
    try:
        from core.risk_manager import get_risk_manager
        risk_mgr = get_risk_manager()
        
        # Test normal trade
        opportunity = {
            'symbol': 'BTC/USDT',
            'buy_ex': 'Bybit',
            'sell_ex': 'KuCoin',
            'qty': 0.001,
            'buy_avg': 50000,
            'sell_avg': 50100,
            'net': 100,
            'roi_pct': 0.2
        }
        
        can_trade, reason = risk_mgr.check_can_trade(opportunity)
        tester.test("Accept normal trade", can_trade, f"Reason: {reason}")
        
        # Test anomalous spread
        opportunity_bad = opportunity.copy()
        opportunity_bad['roi_pct'] = 10.0  # 10% spread is anomalous
        can_trade, reason = risk_mgr.check_can_trade(opportunity_bad)
        tester.test("Reject anomalous spread", not can_trade, f"Reason: {reason}")
        
        # Test exposure limit
        opportunity_large = opportunity.copy()
        opportunity_large['buy_avg'] = 50000
        opportunity_large['qty'] = 100  # $5M exposure - way over limit
        can_trade, reason = risk_mgr.check_can_trade(opportunity_large)
        tester.test("Reject over-exposure", not can_trade, f"Reason: {reason}")
        
        # Test consecutive loss tracking
        for i in range(6):  # 6 losses in a row
            trade_info = {
                'net_profit': -10,
                'buy_exchange': 'Bybit',
                'sell_exchange': 'KuCoin'
            }
            risk_mgr.record_trade(trade_info)
        
        can_trade, reason = risk_mgr.check_can_trade(opportunity)
        tester.test("Block after consecutive losses", not can_trade, f"Reason: {reason}")
        
    except Exception as e:
        tester.test("Risk Manager tests", False, str(e))
    
    return tester


async def test_balance_manager():
    """Test balance manager functionality."""
    tester = IntegrationTester()
    print("\n" + "="*80)
    print("TEST SUITE 5: Balance Manager")
    print("="*80)
    
    try:
        from core.balance_manager import get_balance_manager
        balance_mgr = get_balance_manager()
        
        # Manually set some test balances
        balance_mgr.balances = {
            'Bybit': {'USDT': 1000.0, 'BTC': 0.01},
            'KuCoin': {'USDT': 500.0, 'BTC': 0.005}
        }
        
        # Test sufficient balance
        can_trade, reason = balance_mgr.has_sufficient_balance('Bybit', 'USDT', 100.0)
        tester.test("Accept sufficient balance", can_trade, f"Reason: {reason}")
        
        # Test insufficient balance
        can_trade, reason = balance_mgr.has_sufficient_balance('Bybit', 'USDT', 10000.0)
        tester.test("Reject insufficient balance", not can_trade, f"Reason: {reason}")
        
        # Test missing exchange
        can_trade, reason = balance_mgr.has_sufficient_balance('Binance', 'USDT', 100.0)
        tester.test("Reject missing exchange", not can_trade, f"Reason: {reason}")
        
        # Test record trade
        balance_mgr.record_trade('Bybit', 'KuCoin', 'BTC', 'USDT', 0.001, 50.0, 51.0)
        tester.test("Record trade updates balances", True)
        
        # Check balance was updated
        new_usdt = balance_mgr.balances['Bybit']['USDT']
        tester.test("Buy side balance decreased", new_usdt < 1000.0, f"New balance: {new_usdt}")
        
    except Exception as e:
        tester.test("Balance Manager tests", False, str(e))
    
    return tester


async def test_strategy_manager():
    """Test strategy manager functionality."""
    tester = IntegrationTester()
    print("\n" + "="*80)
    print("TEST SUITE 6: Strategy Manager")
    print("="*80)
    
    try:
        from core.strategy_manager import get_strategy_manager
        strategy_mgr = get_strategy_manager()
        
        # Record some trades
        for i in range(10):
            success = i % 2 == 0
            profit = 0.5 if success else -0.2
            strategy_mgr.record_trade('cross_exchange', success, profit, execution_time=0.5)
        
        # Check stats
        stats = strategy_mgr.strategies['cross_exchange']
        tester.test("Strategy has trades", stats.total_trades == 10)
        tester.test("Win rate calculated", 0 <= stats.win_rate <= 100)
        tester.test("Score calculated", stats.score > 0)
        
        # Test prioritization
        priorities = strategy_mgr.get_strategy_priorities()
        tester.test("Priorities calculated", len(priorities) > 0)
        
    except Exception as e:
        tester.test("Strategy Manager tests", False, str(e))
    
    return tester


async def test_integrated_main():
    """Test the integrated main.py can be imported."""
    tester = IntegrationTester()
    print("\n" + "="*80)
    print("TEST SUITE 7: Integrated Main")
    print("="*80)
    
    try:
        import main_integrated
        tester.test("Import main_integrated", True)
        
        # Check key classes exist
        tester.test("IntegratedArbitrageBot class exists", 
                   hasattr(main_integrated, 'IntegratedArbitrageBot'))
        
    except Exception as e:
        tester.test("Import main_integrated", False, str(e))
    
    return tester


async def main():
    """Run all test suites."""
    print("\n" + "="*80)
    print("COMPREHENSIVE INTEGRATION TEST SUITE")
    print("="*80)
    print("Testing all components and their integration...")
    
    all_testers = []
    
    # Run all test suites
    all_testers.append(await test_imports())
    all_testers.append(await test_component_initialization())
    all_testers.append(await test_configuration())
    all_testers.append(await test_risk_manager())
    all_testers.append(await test_balance_manager())
    all_testers.append(await test_strategy_manager())
    all_testers.append(await test_integrated_main())
    
    # Aggregate results
    total_passed = sum(t.passed for t in all_testers)
    total_failed = sum(t.failed for t in all_testers)
    total_warnings = sum(t.warnings for t in all_testers)
    
    print("\n" + "="*80)
    print("OVERALL TEST SUMMARY")
    print("="*80)
    print(f"✅ Total Passed: {total_passed}")
    print(f"❌ Total Failed: {total_failed}")
    print(f"⚠️  Total Warnings: {total_warnings}")
    print("="*80)
    
    if total_failed == 0:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        print("✅ The bot is ready for testing!")
        return 0
    else:
        print("\n❌ SOME INTEGRATION TESTS FAILED!")
        print("⚠️  Please fix the issues before running the bot.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
