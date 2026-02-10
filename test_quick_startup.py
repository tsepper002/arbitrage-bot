#!/usr/bin/env python3
"""
Quick startup test - Verify the bot can initialize without errors.
This is a dry-run test that doesn't require API keys or network connection.
"""
import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up minimal logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("startup_test")


async def test_quick_startup():
    """Test that bot components can be initialized."""
    logger.info("="*80)
    logger.info("QUICK STARTUP TEST")
    logger.info("="*80)
    
    try:
        # Test basic imports
        logger.info("✓ Testing imports...")
        from core.price_store import PriceStore
        from core.arbitrage import ArbitrageEngine
        from core.balance_manager import get_balance_manager
        from core.risk_manager import get_risk_manager
        from core.state_manager import get_state_manager
        logger.info("✅ All core modules imported successfully")
        
        # Test initialization
        logger.info("✓ Testing initialization...")
        store = PriceStore()
        balance_mgr = get_balance_manager()
        risk_mgr = get_risk_manager()
        state_mgr = get_state_manager()
        engine = ArbitrageEngine(store, risk_manager=risk_mgr)
        logger.info("✅ All components initialized successfully")
        
        # Test state loading
        logger.info("✓ Testing state management...")
        state_mgr.load_state()  # Not async
        logger.info(f"✅ State loaded from: {state_mgr.state_file}")
        
        # Print configuration
        logger.info("✓ Configuration summary...")
        import settings
        print("\n" + settings.get_config_summary())
        
        logger.info("\n" + "="*80)
        logger.info("✅ ALL STARTUP TESTS PASSED!")
        logger.info("="*80)
        logger.info("\nThe bot is ready for testing!")
        logger.info("To run the full bot, use: python main_integrated.py")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ STARTUP TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_quick_startup())
    sys.exit(exit_code)
