#!/usr/bin/env python3
"""
main_integrated.py — Full integration of all advanced features
Enhanced with all modules: REST clients, balance manager, risk manager, 
state persistence, telegram, strategies, auto-rebalancer, and more.
"""

# CRITICAL: Configure UTF-8 encoding FIRST, before ANY other imports!
# This prevents UnicodeEncodeError with emoji on Windows (cp1251 encoding)
import sys
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass  # Graceful fallback if reconfigure not available

# Now safe to import everything else
import asyncio
import logging
import os
from typing import List, Dict, Optional

# CRITICAL: Load .env file BEFORE importing settings
from dotenv import load_dotenv
load_dotenv()  # This loads API keys and other config from .env file

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
from core.smart_capital_allocator import get_smart_allocator

# Professional Infrastructure
from infrastructure.health_monitor import HealthMonitor
from infrastructure.alert_manager import AlertManager
from infrastructure.rate_limiter import RateLimiter
from infrastructure.circuit_breaker_enhanced import CircuitBreakerEnhanced
from infrastructure.metrics_collector import MetricsCollector

# Professional Analytics
from analytics.trade_journal import TradeJournal
from analytics.performance_tracker import PerformanceTracker
from analytics.profit_attribution import ProfitAttributionAnalyzer
from analytics.risk_analytics import RiskAnalytics
from analytics.backtest_engine import BacktestEngine
from analytics.market_intelligence import MarketIntelligence
from analytics.realtime_analytics import RealtimeAnalytics
from analytics.correlation_analyzer import CorrelationAnalyzer
from analytics.custom_dashboard import CustomDashboard

# Professional Features
from professional_features.flash_crash_protector import FlashCrashProtector
from professional_features.wash_trading_filter import WashTradingFilter
from professional_features.orderbook_imbalance_detector import OrderBookImbalanceDetector

# Trading Strategies (Phase 4)
from core.strategies.grid_trading import GridTradingStrategy
from core.strategies.dca_strategy import DCAStrategy
from core.strategies.market_making import MarketMakingStrategy
from core.strategies.pairs_trading import PairsTradingStrategy
from core.strategies.funding_rate_enhanced import FundingRateEnhancedStrategy
from core.strategies.volatility_arb import VolatilityArbitrageStrategy
from core.strategies.index_arb import IndexArbitrageStrategy
from core.strategies.spread_betting import SpreadBettingStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.breakout_strategy import BreakoutStrategy

# Professional Execution (Phase 5)
from professional_features.twap_engine import TWAPEngine
from professional_features.vwap_engine import VWAPEngine
from professional_features.iceberg_order_detector import IcebergOrderDetector
from professional_features.order_flow_tracker import OrderFlowTracker

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

# Configure logging with separate levels for console and file
# Console: INFO and above (clean output, no DEBUG spam)
# File: DEBUG and above (full details for debugging)

# Create UTF-8 compatible stream wrapper for Windows console
# This ensures emoji work even with cp1251 encoding
class UTF8StreamWrapper:
    """Wrapper to handle UTF-8 output on Windows console with cp1251 encoding."""
    def __init__(self, stream):
        self.stream = stream
        self.encoding = 'utf-8'
        
    def write(self, message):
        """Write message with UTF-8 support and graceful error handling."""
        if isinstance(message, bytes):
            message = message.decode('utf-8', errors='replace')
        try:
            # Try direct write first (works if console supports UTF-8)
            self.stream.write(message)
        except UnicodeEncodeError:
            # Fallback: replace unsupported characters with ?
            try:
                # Try encoding with errors='replace' to replace emoji with ?
                encoded = message.encode(self.stream.encoding if hasattr(self.stream, 'encoding') else 'cp1251', errors='replace')
                self.stream.write(encoded.decode(self.stream.encoding if hasattr(self.stream, 'encoding') else 'cp1251', errors='replace'))
            except Exception:
                # Ultimate fallback: strip all non-ASCII
                self.stream.write(message.encode('ascii', errors='replace').decode('ascii'))
        except Exception:
            pass  # Ignore any other errors
    
    def flush(self):
        """Flush the underlying stream."""
        try:
            self.stream.flush()
        except Exception:
            pass

# Use UTF-8 wrapper for console handler to prevent UnicodeEncodeError
console_handler = logging.StreamHandler(UTF8StreamWrapper(sys.stderr))
console_handler.setLevel(logging.INFO)  # Only INFO+ in console
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

# File handler with UTF-8 encoding
file_handler = logging.FileHandler("arbitrage_bot.log", encoding='utf-8')
file_handler.setLevel(logging.DEBUG)  # All logs in file
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,  # Root level must be DEBUG to capture all
    handlers=[console_handler, file_handler]
)
logger = logging.getLogger("arbitrage_bot")

# Force all exchange loggers to INFO level (not DEBUG) for console
# This prevents WebSocket modules from spamming console with DEBUG messages
for logger_name in ['kucoin_ws', 'bybit_ws', 'htx_ws', 'mexc_ws', 'binance_ws', 'arbitrage_ws']:
    exchange_logger = logging.getLogger(logger_name)
    exchange_logger.setLevel(logging.INFO)  # Only INFO+ will be logged


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
        
        # Professional Infrastructure
        self.health_monitor = None
        self.alert_manager = None
        self.rate_limiter = None
        self.circuit_breaker = None
        self.metrics_collector = None
        
        # Professional Analytics
        self.trade_journal = None
        self.performance_tracker = None
        self.profit_attribution = None
        self.risk_analytics = None
        self.backtest_engine = None
        self.market_intelligence = None
        self.realtime_analytics = None
        self.correlation_analyzer = None
        self.custom_dashboard = None
        
        # Professional Features
        self.flash_crash_protector = None
        self.wash_trading_filter = None
        self.orderbook_imbalance_detector = None
        
        # Trading Strategies (Phase 4)
        self.grid_trading = None
        self.dca_strategy = None
        self.market_making = None
        self.pairs_trading = None
        self.funding_rate_enhanced = None
        self.volatility_arb = None
        self.index_arb = None
        self.spread_betting = None
        self.momentum_strategy = None
        self.breakout_strategy = None
        
        # Professional Execution (Phase 5)
        self.twap_engine = None
        self.vwap_engine = None
        self.iceberg_detector = None
        self.order_flow_tracker = None
        
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
                self.balance_manager.rest_clients = self.rest_clients  # Set rest_clients before initialize
                await self.balance_manager.initialize()  # Call without arguments
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
            
            # Smart Capital Allocator
            self.capital_allocator = get_smart_allocator(self.balance_manager)
            logger.info("✅ Smart Capital Allocator initialized")
            self.capital_allocator.print_allocation_summary()
            
            # Professional Infrastructure
            logger.info("\n🔬 Initializing Professional Infrastructure...")
            
            # Health Monitor
            self.health_monitor = HealthMonitor()
            logger.info("✅ Health Monitor initialized")
            
            # Alert Manager
            self.alert_manager = AlertManager()
            logger.info("✅ Alert Manager initialized")
            
            # Rate Limiter (10 requests per second with burst capacity of 20)
            self.rate_limiter = RateLimiter(rate=10.0, capacity=20)
            logger.info("✅ Rate Limiter initialized (10/sec, burst 20)")
            
            # Circuit Breaker (5 failures triggers open, 60s timeout)
            self.circuit_breaker = CircuitBreakerEnhanced(failure_threshold=5, timeout=60)
            logger.info("✅ Circuit Breaker initialized (threshold: 5, timeout: 60s)")
            
            # Metrics Collector
            self.metrics_collector = MetricsCollector()
            logger.info("✅ Metrics Collector initialized")
            
            # Professional Analytics
            logger.info("\n📊 Initializing Professional Analytics...")
            
            # Trade Journal
            self.trade_journal = TradeJournal()
            logger.info("✅ Trade Journal initialized")
            
            # Performance Tracker
            self.performance_tracker = PerformanceTracker()
            logger.info("✅ Performance Tracker initialized")
            
            # Profit Attribution
            self.profit_attribution = ProfitAttributionAnalyzer()
            logger.info("✅ Profit Attribution initialized")
            
            # Risk Analytics
            self.risk_analytics = RiskAnalytics()
            logger.info("✅ Risk Analytics initialized")
            
            # Phase 6: Additional Analytics Modules (5 modules)
            logger.info("\n📊 Initializing Additional Analytics...")
            
            # Backtest Engine
            self.backtest_engine = BacktestEngine(
                initial_capital=10000  # Default backtest capital
            )
            logger.info("✅ Backtest Engine initialized")
            
            # Market Intelligence
            self.market_intelligence = MarketIntelligence()
            logger.info("✅ Market Intelligence initialized")
            
            # Realtime Analytics
            self.realtime_analytics = RealtimeAnalytics()
            logger.info("✅ Realtime Analytics initialized")
            
            # Correlation Analyzer
            self.correlation_analyzer = CorrelationAnalyzer()
            logger.info("✅ Correlation Analyzer initialized")
            
            # Custom Dashboard
            self.custom_dashboard = CustomDashboard()
            logger.info("✅ Custom Dashboard initialized")
            
            logger.info("✅ All 5 Additional Analytics Modules initialized!")
            
            # Professional Features
            logger.info("\n🛡️  Initializing Professional Risk Features...")
            
            # Flash Crash Protector
            self.flash_crash_protector = FlashCrashProtector()
            logger.info("✅ Flash Crash Protector initialized")
            
            # Wash Trading Filter
            self.wash_trading_filter = WashTradingFilter()
            logger.info("✅ Wash Trading Filter initialized")
            
            # Orderbook Imbalance Detector
            self.orderbook_imbalance_detector = OrderBookImbalanceDetector()
            logger.info("✅ Orderbook Imbalance Detector initialized")
            
            logger.info("\n🎯 All professional components initialized successfully!")
            
        except Exception as e:
            logger.error(f"❌ Error initializing managers: {e}")
            raise
    
    async def _run_startup_validation(self):
        """Run comprehensive startup validation."""
        try:
            self.startup_validator = get_startup_validator(
                exchanges=list(self.rest_clients.keys()) if self.rest_clients else [],
                rest_clients=self.rest_clients,
                ws_connections=self.ws_connections if hasattr(self, 'ws_connections') else {},
                balance_manager=self.balance_manager,
                risk_manager=self.risk_manager,
                state_manager=self.state_manager,
                price_store=self.price_store if hasattr(self, 'price_store') else None,
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
            
            # MexcWS now accepts price_store and loop like other exchanges
            mexc = MexcWS(
                symbol=symbols[0] if symbols else "BTC-USDT",  # First symbol
                price_store=self.store,
                loop=self.loop,
                api_key=None,
                secret_key=None,
                ws_url="wss://contract.mexc.com/ws",
                exchange_name="MEXC"
            )
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
            
            # Phase 4: Initialize Trading Strategies (10 modules)
            logger.info("\n🎯 Initializing Trading Strategies...")
            
            # 1. Grid Trading Strategy
            self.grid_trading = GridTradingStrategy(
                exchange="Bybit",  # Use first available exchange
                symbol="BTC-USDT",  # Default symbol
                grid_levels=10,
                price_range_pct=0.1,
                capital_per_level=50.0
            )
            logger.info("✅ Grid Trading Strategy initialized")
            
            # 2. DCA (Dollar Cost Averaging) Strategy
            self.dca_strategy = DCAStrategy(
                exchange="Bybit",
                symbol="BTC-USDT",
                amount_per_buy=50.0,
                interval_hours=24,
                max_position_usdt=1000.0
            )
            logger.info("✅ DCA Strategy initialized")
            
            # 3. Market Making Strategy
            self.market_making = MarketMakingStrategy(
                exchange_client="Bybit",
                symbol="BTC-USDT",
                spread_pct=0.002,
                order_size_usdt=100.0,
                max_inventory_usdt=500.0,
                refresh_interval_sec=10
            )
            logger.info("✅ Market Making Strategy initialized")
            
            # 4. Pairs Trading Strategy
            self.pairs_trading = PairsTradingStrategy(
                exchange="Bybit",
                pair1="BTC-USDT",
                pair2="ETH-USDT",
                lookback=60,
                entry_z=2.0,
                exit_z=0.5
            )
            logger.info("✅ Pairs Trading Strategy initialized")
            
            # 5. Enhanced Funding Rate Strategy
            self.funding_rate_enhanced = FundingRateEnhancedStrategy(
                exchange_client="Bybit",
                symbol="BTC-USDT",
                min_funding_rate=0.0001,
                position_size_usdt=1000.0,
                hold_duration_hours=8
            )
            logger.info("✅ Enhanced Funding Rate Strategy initialized")
            
            # 6. Volatility Arbitrage Strategy
            self.volatility_arb = VolatilityArbitrageStrategy(
                exchange_client=self.rest_clients.get("Bybit"),
                symbol="BTC-USDT",
                lookback_period=30,
                vol_threshold=0.2,
                position_size_usdt=500.0
            )
            logger.info("✅ Volatility Arbitrage Strategy initialized")
            
            # 7. Index Arbitrage Strategy
            self.index_arb = IndexArbitrageStrategy(
                exchange="Bybit",
                index_symbol="BTC-USDT",
                components=[("BTC-USDT", 1.0)],
                threshold_pct=0.005
            )
            logger.info("✅ Index Arbitrage Strategy initialized")
            
            # 8. Spread Betting Strategy
            self.spread_betting = SpreadBettingStrategy(
                exchange_client="Bybit",
                pair1="BTC-USDT",
                pair2="ETH-USDT",
                lookback_period=100
            )
            logger.info("✅ Spread Betting Strategy initialized")
            
            # 9. Momentum Strategy
            self.momentum_strategy = MomentumStrategy(
                rsi_period=14
            )
            logger.info("✅ Momentum Strategy initialized")
            
            # 10. Breakout Strategy
            self.breakout_strategy = BreakoutStrategy(
                config={
                    'lookback_period': 50,
                    'volume_threshold': 1.5,
                    'breakout_threshold': 0.001,
                    'min_touches': 3
                }
            )
            logger.info("✅ Breakout Strategy initialized")
            
            logger.info("✅ All 10 Trading Strategies initialized successfully!")
            
            # Phase 5: Professional Execution Modules (4 modules)
            logger.info("\n🎯 Initializing Professional Execution Modules...")
            
            # 1. TWAP Engine (Time-Weighted Average Price)
            self.twap_engine = TWAPEngine()
            logger.info("✅ TWAP Engine initialized")
            
            # 2. VWAP Engine (Volume-Weighted Average Price)
            self.vwap_engine = VWAPEngine()
            logger.info("✅ VWAP Engine initialized")
            
            # 3. Iceberg Order Detector
            self.iceberg_detector = IcebergOrderDetector()
            logger.info("✅ Iceberg Order Detector initialized")
            
            # 4. Order Flow Tracker
            self.order_flow_tracker = OrderFlowTracker()
            logger.info("✅ Order Flow Tracker initialized")
            
            logger.info("✅ All 4 Professional Execution Modules initialized!")
            
            # Triangular Arbitrage Engine
            self.triangular_engine = get_triangular_engine(
                price_store=self.store,
                order_executor=None,  # Will be set later
                exchange_config={},    # Empty config for now
                enabled_exchanges=["Bybit", "KuCoin", "HTX", "MEXC"]
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
                strategy_manager=self.strategy_manager,
                flash_crash_protector=self.flash_crash_protector,
                wash_trading_filter=self.wash_trading_filter,
                orderbook_imbalance_detector=self.orderbook_imbalance_detector,
                trade_journal=self.trade_journal,
                profit_attribution=self.profit_attribution,
                metrics_collector=self.metrics_collector
            )
            logger.info("✅ Main Arbitrage Engine initialized with professional components")
            
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
                resource_task = asyncio.create_task(self.resource_monitor.start_monitoring())
                self.tasks.append(resource_task)
                logger.info("✅ Resource monitor task started")
            
            # Professional health monitoring task
            if self.health_monitor:
                health_task = asyncio.create_task(self._health_monitor_loop())
                self.tasks.append(health_task)
                logger.info("✅ Professional health monitor task started")
            
            # Professional analytics task
            if self.performance_tracker:
                analytics_task = asyncio.create_task(self._analytics_loop())
                self.tasks.append(analytics_task)
                logger.info("✅ Professional analytics task started")
            
            # State persistence task
            if self.state_manager:
                state_task = asyncio.create_task(self._state_save_loop())
                self.tasks.append(state_task)
                logger.info("✅ State persistence task started")
            
            # Telegram monitoring task
            if self.telegram_bot:
                telegram_task = asyncio.create_task(self.telegram_bot.start_monitoring_loop(self))
                self.tasks.append(telegram_task)
                logger.info("✅ Telegram monitoring task started")
            
            # Auto-rebalancer task
            if self.rebalancer:
                rebalance_task = asyncio.create_task(self.rebalancer.monitoring_loop())
                self.tasks.append(rebalance_task)
                logger.info("✅ Auto-rebalancer task started")
            
            # Triangular arbitrage task
            # Note: Triangular engine is integrated into main engine, no separate scan needed
            # if self.triangular_engine:
            #     triangular_task = asyncio.create_task(self.triangular_engine.scan_loop(symbols))
            #     self.tasks.append(triangular_task)
            #     logger.info("✅ Triangular arbitrage task started")
            
            # Main arbitrage engine task
            engine_task = asyncio.create_task(self.engine.run(symbols))
            self.tasks.append(engine_task)
            logger.info("✅ Main arbitrage engine started")
            
            logger.info(f"\n🎉 Bot fully operational with {len(self.tasks)} background tasks!")
            if self.telegram_bot:
                await self.telegram_bot.send_message("✅ Bot fully operational!")
            
            # Wait for all tasks (with return_exceptions to prevent premature exit)
            await asyncio.gather(*self.tasks, return_exceptions=True)
            
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
                # Print detailed strategy information
                if self.strategy_manager:
                    self.strategy_manager.print_all_strategies_info()
                
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
                    
                    self.state_manager.save_state()  # Not async, no await needed
                
        except asyncio.CancelledError:
            # Save one last time before exit
            if self.state_manager:
                self.state_manager.save_state()  # Not async, no await needed
                logger.info("✅ Final state saved")
            return
    
    async def _health_monitor_loop(self):
        """Professional health monitoring loop."""
        try:
            while True:
                await asyncio.sleep(60)  # Check health every minute
                
                if self.health_monitor:
                    # Get full health status
                    health_status = self.health_monitor.get_full_status()
                    
                    # Check system health
                    sys_health = health_status['system']
                    if not sys_health['healthy']:
                        msg = f"⚠️ System health degraded! CPU: {sys_health['cpu_percent']:.1f}%, Memory: {sys_health['memory_percent']:.1f}%"
                        logger.warning(msg)
                        if self.alert_manager:
                            self.alert_manager.send_alert('WARNING', msg, ['log', 'telegram'])
                    
                    # Log health summary
                    uptime_hours = health_status['uptime']['uptime_hours']
                    logger.info(f"💚 Health check: System OK, Uptime: {uptime_hours:.1f}h")
                    
        except asyncio.CancelledError:
            return
    
    async def _analytics_loop(self):
        """Professional analytics monitoring loop."""
        try:
            while True:
                await asyncio.sleep(300)  # Update analytics every 5 minutes
                
                if self.performance_tracker and self.balance_manager:
                    # Update balance in performance tracker
                    total_balance = self.balance_manager.get_total_balance()
                    if total_balance > 0:
                        self.performance_tracker.update_balance(total_balance)
                        
                        # Get and log performance statistics
                        stats = self.performance_tracker.get_statistics()
                        if stats['data_points'] > 10:
                            logger.info(
                                f"📊 Performance: Return: {stats['total_return_pct']:.2f}%, "
                                f"Sharpe: {stats['sharpe_ratio']:.2f}, "
                                f"Max DD: {stats['max_drawdown_pct']:.2f}%"
                            )
                
                # Log trade journal summary
                if self.trade_journal:
                    summary = self.trade_journal.get_summary()
                    if summary.get('total_trades', 0) > 0:
                        logger.info(
                            f"📓 Trade Journal: {summary['total_trades']} trades, "
                            f"Net profit: ${summary['net_profit']:.2f}"
                        )
                
                # Log profit attribution
                if self.profit_attribution:
                    by_strategy = self.profit_attribution.by_strategy()
                    if by_strategy:
                        logger.info(f"💰 Profit by strategy: {by_strategy}")
                
        except asyncio.CancelledError:
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
            # Print final strategy summary
            if self.strategy_manager:
                self.strategy_manager.print_all_strategies_info()
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
                exchange_name = getattr(exchange, 'name', getattr(exchange, 'exchange_name', str(type(exchange).__name__)))
                
                # Special handling for Binance (uses running flag)
                if hasattr(exchange, '_stopping') and hasattr(exchange, 'running'):
                    exchange._stopping = True
                    exchange.running = False
                    logger.debug(f"{exchange_name} stopping flag set")
                
                # Check if exchange has a stop method
                if not hasattr(exchange, 'stop'):
                    logger.debug(f"{exchange_name} has no stop method, skipping")
                    continue
                
                # Call stop method (handle both sync and async)
                stop_method = exchange.stop()
                if asyncio.iscoroutine(stop_method):
                    await stop_method
                # else: synchronous method already executed
                    
            except Exception as e:
                exchange_name = getattr(exchange, 'name', getattr(exchange, 'exchange_name', str(type(exchange).__name__)))
                logger.error(f"Error stopping {exchange_name}: {e}")
        
        # Final state save
        if self.state_manager:
            self.state_manager.save_state()  # Not async, no await needed
        
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
