#!/usr/bin/env python3
"""
main_integrated.py — Full integration of all advanced features
Enhanced with all modules: REST clients, balance manager, risk manager, 
state persistence, telegram, strategies, auto-rebalancer, and more.
"""
import asyncio
import logging
import sys
import os
from typing import List, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Core modules
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
from core.windows_optimizer import setup_windows_optimizations, WindowsOptimizer

# Exchange modules
from exchanges.bybit_ws import BybitWS
from exchanges.kucoin_ws import KucoinWS
from exchanges.htx_ws import HtxWS
from exchanges.mexc_ws import MexcWS
from exchanges.binance_ws import BinanceWS

# REST clients
from exchanges.rest_clients.bybit_client import BybitRESTClient
from exchanges.rest_clients.kucoin_client import KuCoinRESTClient
from exchanges.rest_clients.htx_client import HTXRESTClient
from exchanges.rest_clients.mexc_client import MEXCRESTClient
from exchanges.rest_clients.binance_client import BinanceRESTClient

import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("arbitrage_bot.log")
    ]
)
logger = logging.getLogger("arbitrage_bot")


class IntegratedArbitrageBot:
    """Fully integrated arbitrage bot with all advanced features."""
    
    def __init__(self):
        self.loop = None
        self.store = None
        self.exchanges = []
        self.rest_clients: Dict[str, any] = {}
        self.balance_manager = None
        self.risk_manager = None
        self.state_manager = None
        self.telegram_bot = None
        self.resource_monitor = None
        self.triangular_engine = None
        self.order_selector = None
        self.strategy_manager = None
        self.rebalancer = None
        self.startup_validator = None
        self.windows_optimizer: Optional[WindowsOptimizer] = None
        
        self.engine = None
        self.tasks = []
        
    async def initialize(self):
        """Initialize all components."""
        logger.info("="*80)
        logger.info("🚀 STARTING INTEGRATED ARBITRAGE BOT")
        logger.info("="*80)
        
        # Print configuration
        logger.info("\n" + settings.get_config_summary())
        
        # Phase 1: Windows Optimization
        logger.info("\n📊 Phase 1: Applying Windows Optimizations...")
        self.windows_optimizer = setup_windows_optimizations()
        if self.windows_optimizer:
            logger.info("✅ Windows optimizations applied")
        else:
            logger.info("ℹ️  Running on non-Windows platform (optimizations skipped)")
        
        # Phase 2: Initialize REST clients
        logger.info("\n🔌 Phase 2: Initializing REST API Clients...")
        await self._initialize_rest_clients()
        
        # Phase 3: Initialize managers
        logger.info("\n⚙️  Phase 3: Initializing Core Managers...")
        await self._initialize_managers()
        
        # Phase 4: Startup validation
        logger.info("\n🔍 Phase 4: Running Startup Validation...")
        validation_passed = await self._run_startup_validation()
        if not validation_passed:
            logger.error("❌ Startup validation failed. Exiting.")
            return False
        
        # Phase 5: Initialize exchanges and price store
        logger.info("\n📡 Phase 5: Initializing Exchange Connections...")
        await self._initialize_exchanges()
        
        # Phase 6: Initialize strategies
        logger.info("\n🎯 Phase 6: Initializing Trading Strategies...")
        await self._initialize_strategies()
        
        logger.info("\n✅ All components initialized successfully!")
        return True
    
    async def _initialize_rest_clients(self):
        """Initialize authenticated REST API clients for all exchanges."""
        try:
            # Bybit
            bybit_key = os.getenv("ARB_BYBIT_KEY", "")
            bybit_secret = os.getenv("ARB_BYBIT_SECRET", "")
            if bybit_key and bybit_secret:
                self.rest_clients["Bybit"] = BybitRESTClient(bybit_key, bybit_secret)
                logger.info("✅ Bybit REST client initialized")
            else:
                logger.warning("⚠️  Bybit API keys not found (live trading disabled for Bybit)")
            
            # KuCoin
            kucoin_key = os.getenv("ARB_KUCOIN_KEY", "")
            kucoin_secret = os.getenv("ARB_KUCOIN_SECRET", "")
            kucoin_pass = os.getenv("ARB_KUCOIN_PASSPHRASE", "")
            if kucoin_key and kucoin_secret and kucoin_pass:
                self.rest_clients["KuCoin"] = KuCoinRESTClient(kucoin_key, kucoin_secret, kucoin_pass)
                logger.info("✅ KuCoin REST client initialized")
            else:
                logger.warning("⚠️  KuCoin API keys not found (live trading disabled for KuCoin)")
            
            # HTX
            htx_key = os.getenv("ARB_HTX_KEY", "")
            htx_secret = os.getenv("ARB_HTX_SECRET", "")
            if htx_key and htx_secret:
                self.rest_clients["HTX"] = HTXRESTClient(htx_key, htx_secret)
                logger.info("✅ HTX REST client initialized")
            else:
                logger.warning("⚠️  HTX API keys not found (live trading disabled for HTX)")
            
            # MEXC
            mexc_key = os.getenv("ARB_MEXC_KEY", "")
            mexc_secret = os.getenv("ARB_MEXC_SECRET", "")
            if mexc_key and mexc_secret:
                self.rest_clients["MEXC"] = MEXCRESTClient(mexc_key, mexc_secret)
                logger.info("✅ MEXC REST client initialized")
            else:
                logger.warning("⚠️  MEXC API keys not found (live trading disabled for MEXC)")
            
            # Binance
            binance_key = os.getenv("ARB_BINANCE_KEY", "")
            binance_secret = os.getenv("ARB_BINANCE_SECRET", "")
            if binance_key and binance_secret:
                self.rest_clients["Binance"] = BinanceRESTClient(binance_key, binance_secret)
                logger.info("✅ Binance REST client initialized")
            else:
                logger.warning("⚠️  Binance API keys not found (live trading disabled for Binance)")
            
            logger.info(f"📊 Total REST clients: {len(self.rest_clients)}/5")
            
        except Exception as e:
            logger.error(f"❌ Error initializing REST clients: {e}")
            raise
    
    async def _initialize_managers(self):
        """Initialize all manager components."""
        try:
            # State Manager
            self.state_manager = get_state_manager()
            self.state_manager.load_state()  # This is not async, don't await
            logger.info("✅ State Manager initialized (state loaded)")
            
            # Balance Manager
            self.balance_manager = get_balance_manager()
            if self.rest_clients:
                await self.balance_manager.initialize(self.rest_clients)
                logger.info("✅ Balance Manager initialized (balances fetched)")
                self.balance_manager.print_summary()
            else:
                logger.warning("⚠️  No REST clients available, Balance Manager in limited mode")
            
            # Risk Manager
            self.risk_manager = get_risk_manager()
            # Restore daily stats from state
            if self.state_manager.state.get("daily_pnl"):
                self.risk_manager.daily_pnl = self.state_manager.state["daily_pnl"]
            logger.info("✅ Risk Manager initialized")
            
            # Telegram Bot
            telegram_token = os.getenv("ARB_TELEGRAM_TOKEN", "")
            telegram_chat_id = os.getenv("ARB_TELEGRAM_CHAT_ID", "")
            if telegram_token and telegram_chat_id:
                self.telegram_bot = get_telegram_bot(telegram_token, telegram_chat_id)
                await self.telegram_bot.send_message("🚀 Arbitrage bot starting up...")
                logger.info("✅ Telegram Bot initialized")
            else:
                logger.warning("⚠️  Telegram credentials not found (notifications disabled)")
            
            # Resource Monitor
            self.resource_monitor = get_resource_monitor()
            logger.info("✅ Resource Monitor initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing managers: {e}")
            raise
    
    async def _run_startup_validation(self):
        """Run comprehensive startup validation."""
        try:
            self.startup_validator = get_startup_validator(
                rest_clients=self.rest_clients,
                balance_manager=self.balance_manager,
                risk_manager=self.risk_manager,
                state_manager=self.state_manager,
                telegram_bot=self.telegram_bot
            )
            
            # Run all validation checks
            all_passed, summary = await self.startup_validator.validate_all()
            
            # Print summary
            print("\n" + "="*80)
            print("STARTUP VALIDATION REPORT")
            print("="*80)
            print(summary)
            print("="*80)
            
            if not all_passed:
                if self.telegram_bot:
                    await self.telegram_bot.send_message(f"⚠️ Startup validation failed:\n{summary}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error during startup validation: {e}")
            return False
    
    async def _initialize_exchanges(self):
        """Initialize WebSocket connections to all exchanges."""
        try:
            self.loop = asyncio.get_running_loop()
            self.store = PriceStore()
            
            symbols: List[str] = settings.TRADING_SYMBOLS
            logger.info(f"📈 Tracking {len(symbols)} symbols: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}")
            
            # Initialize with staggered start
            stagger = 0.1
            
            bybit = BybitWS(symbols, self.store, self.loop, exchange_name="Bybit", stagger_start=stagger)
            await asyncio.sleep(stagger)
            
            kucoin = KucoinWS(symbols, self.store, self.loop, exchange_name="KuCoin", stagger_start=stagger)
            await asyncio.sleep(stagger)
            
            htx = HtxWS(symbols, self.store, self.loop, exchange_name="HTX", stagger_start=stagger)
            await asyncio.sleep(stagger)
            
            mexc = MexcWS(symbols, self.store, self.loop, exchange_name="MEXC", stagger_start=stagger)
            await asyncio.sleep(stagger)
            
            binance = BinanceWS(symbols, self.store, self.loop, exchange_name="Binance", stagger_start=stagger)
            
            self.exchanges = [bybit, kucoin, htx, mexc, binance]
            logger.info(f"✅ All {len(self.exchanges)} exchange WebSockets initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing exchanges: {e}")
            raise
    
    async def _initialize_strategies(self):
        """Initialize all trading strategies."""
        try:
            # Strategy Manager
            self.strategy_manager = get_strategy_manager()
            logger.info("✅ Strategy Manager initialized")
            
            # Order Type Selector
            self.order_selector = get_order_type_selector(self.rest_clients)
            logger.info("✅ Smart Order Selector initialized")
            
            # Triangular Arbitrage Engine
            self.triangular_engine = get_triangular_engine(
                store=self.store,
                rest_clients=self.rest_clients,
                balance_manager=self.balance_manager,
                risk_manager=self.risk_manager,
                strategy_manager=self.strategy_manager
            )
            logger.info("✅ Triangular Arbitrage Engine initialized")
            
            # Auto-Rebalancer
            if self.balance_manager and len(self.rest_clients) >= 2:
                self.rebalancer = get_auto_rebalancer(
                    balance_manager=self.balance_manager,
                    rest_clients=self.rest_clients,
                    telegram_bot=self.telegram_bot
                )
                logger.info("✅ Auto-Rebalancer initialized")
            else:
                logger.warning("⚠️  Auto-Rebalancer disabled (need at least 2 REST clients)")
            
            # Main Arbitrage Engine with integrated components
            executor = OrderExecutor(
                dry_run=settings.DRY_RUN,
                rest_clients=self.rest_clients,
                balance_manager=self.balance_manager
            )
            
            self.engine = ArbitrageEngine(
                store=self.store,
                executor=executor,
                risk_manager=self.risk_manager,
                strategy_manager=self.strategy_manager
            )
            logger.info("✅ Main Arbitrage Engine initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing strategies: {e}")
            raise
    
    async def run(self):
        """Main run loop."""
        try:
            symbols = settings.TRADING_SYMBOLS
            
            # Start background tasks
            logger.info("\n🔄 Starting background tasks...")
            
            # Monitoring task
            monitor_task = asyncio.create_task(self._monitor_loop())
            self.tasks.append(monitor_task)
            
            # Balance sync task
            if self.balance_manager and self.rest_clients:
                balance_task = asyncio.create_task(self.balance_manager.monitoring_loop())
                self.tasks.append(balance_task)
                logger.info("✅ Balance sync task started")
            
            # Resource monitoring task
            if self.resource_monitor:
                resource_task = asyncio.create_task(self.resource_monitor.monitoring_loop())
                self.tasks.append(resource_task)
                logger.info("✅ Resource monitor task started")
            
            # State persistence task
            if self.state_manager:
                state_task = asyncio.create_task(self._state_save_loop())
                self.tasks.append(state_task)
                logger.info("✅ State persistence task started")
            
            # Auto-rebalancer task
            if self.rebalancer:
                rebalance_task = asyncio.create_task(self.rebalancer.monitoring_loop())
                self.tasks.append(rebalance_task)
                logger.info("✅ Auto-rebalancer task started")
            
            # Triangular arbitrage task
            if self.triangular_engine:
                triangular_task = asyncio.create_task(self.triangular_engine.scan_loop(symbols))
                self.tasks.append(triangular_task)
                logger.info("✅ Triangular arbitrage task started")
            
            # Main arbitrage engine task
            engine_task = asyncio.create_task(self.engine.run(symbols))
            self.tasks.append(engine_task)
            logger.info("✅ Main arbitrage engine started")
            
            logger.info(f"\n🎉 Bot fully operational with {len(self.tasks)} background tasks!")
            if self.telegram_bot:
                await self.telegram_bot.send_message("✅ Bot fully operational!")
            
            # Wait for all tasks
            await asyncio.gather(*self.tasks)
            
        except asyncio.CancelledError:
            logger.info("Tasks cancelled, shutting down...")
        except Exception as e:
            logger.error(f"❌ Error in main run loop: {e}")
            if self.telegram_bot:
                await self.telegram_bot.send_message(f"❌ Critical error: {str(e)[:200]}")
            raise
    
    async def _monitor_loop(self):
        """Monitor and log store statistics."""
        interval = settings.MONITOR_INTERVAL_SEC
        try:
            while True:
                await asyncio.sleep(interval)
                
                snap = self.store.snapshot()
                if snap:
                    total_exchanges = sum(len(exmap) for exmap in snap.values())
                    logger.info(f"📊 [STORE] {len(snap)} symbols, {total_exchanges} exchange connections")
                
                # Print strategy performance
                if self.strategy_manager:
                    self.strategy_manager.print_summary()
                
        except asyncio.CancelledError:
            return
    
    async def _state_save_loop(self):
        """Periodically save state."""
        try:
            while True:
                await asyncio.sleep(30)  # Save every 30 seconds
                
                if self.state_manager:
                    # Update state with current info
                    if self.risk_manager:
                        self.state_manager.state["daily_pnl"] = self.risk_manager.daily_pnl
                    if self.balance_manager:
                        self.state_manager.state["balances"] = self.balance_manager.balances
                    
                    await self.state_manager.save_state()
                
        except asyncio.CancelledError:
            # Save one last time before exit
            if self.state_manager:
                await self.state_manager.save_state()
                logger.info("✅ Final state saved")
            return
    
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("\n🛑 Shutting down gracefully...")
        
        # Cancel all background tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to finish
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Print final statistics
        if self.engine:
            logger.info("\n" + "="*80)
            logger.info("FINAL STATISTICS")
            logger.info("="*80)
            self.engine.executor.print_statistics()
            if self.strategy_manager:
                self.strategy_manager.print_summary()
            logger.info("="*80)
        
        # Close REST client sessions
        logger.info("Closing REST client sessions...")
        for name, client in self.rest_clients.items():
            try:
                await client.close()
                logger.info(f"✅ {name} REST client closed")
            except Exception as e:
                logger.error(f"Error closing {name}: {e}")
        
        # Stop exchange connections
        logger.info("Stopping WebSocket connections...")
        for exchange in self.exchanges:
            try:
                exchange.stop()
            except Exception as e:
                logger.error(f"Error stopping {exchange}: {e}")
        
        # Final state save
        if self.state_manager:
            await self.state_manager.save_state()
        
        # Send final Telegram notification
        if self.telegram_bot:
            await self.telegram_bot.send_message("🛑 Bot shut down successfully")
        
        logger.info("✅ Shutdown complete")


async def main():
    """Main entry point."""
    bot = IntegratedArbitrageBot()
    
    try:
        # Initialize all components
        success = await bot.initialize()
        if not success:
            logger.error("Initialization failed, exiting...")
            return 1
        
        # Run the bot
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  KeyboardInterrupt received")
    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        return 1
    finally:
        await bot.shutdown()
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
