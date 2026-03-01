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
import argparse
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
from core.exchange_config import EXCHANGE_PARAMS
from core.strategy_dispatcher import StrategyDispatcher  # NEW: All 14 strategies!
from core.signal_allocator import SignalAllocator  # Signal-based inventory management

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

# ML modules
from ml.market_regime_detector import MarketRegimeDetector
from ml.ml_spread_predictor import MLSpreadPredictor
from ml.auto_parameter_optimizer import AutoParameterOptimizer
from ml.volatility_forecaster import VolatilityForecaster
from ml.neural_network_predictor import NeuralNetworkPredictor
from ml.reinforcement_learning_agent import ReinforcementLearningAgent
from ml.slippage_predictor import SlippagePredictor
from ml.auto_parameter_tuner import AutoParameterTuner
try:
    from ml.pattern_recognition import PatternRecognition
except ImportError:
    PatternRecognition = None
try:
    from ml.market_adaptive_strategy import MarketAdaptiveStrategy
except ImportError:
    MarketAdaptiveStrategy = None
try:
    from ml.ml_model_trainer import MLModelTrainer
except ImportError:
    MLModelTrainer = None

# Fee optimization
from core.fee_optimizer import FeeOptimizer

# Exchange modules
from exchanges.bybit_ws import BybitWS
from exchanges.kucoin_ws import KucoinWS
from exchanges.htx_ws import HtxWS
from exchanges.mexc import MEXC
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
    handlers=[console_handler, file_handler],
    force=True  # Override any basicConfig calls from exchange modules
)
logger = logging.getLogger("arbitrage_bot")

# Force all exchange loggers to INFO level (not DEBUG) for console
# This prevents WebSocket modules from spamming console with DEBUG messages
for logger_name in ['kucoin_ws', 'bybit_ws', 'htx_ws', 'mexc_ws', 'binance_ws', 'arbitrage_ws', 'MEXC', 'websockets', 'exchange_config', 'arbitrage_engine']:
    exchange_logger = logging.getLogger(logger_name)
    exchange_logger.setLevel(logging.INFO)  # Only INFO+ will be logged


class IntegratedArbitrageBot:
    """Fully integrated arbitrage bot with all advanced features."""
    
    def __init__(self):
        self.loop = None
        self.store = None
        self.exchanges = []
        self._mexc_task = None  # MEXC uses asyncio task instead of thread
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
        
        # ML modules (Phase 6)
        self.volatility_forecaster = None
        self.nn_predictor = None
        self.rl_agent = None
        self.slippage_predictor = None
        self.auto_parameter_tuner = None
        self.pattern_recognition = None
        self.market_adaptive_strategy = None
        self.ml_model_trainer = None
        
        # Strategy Dispatcher (NEW: All 14 strategies!)
        self.strategy_dispatcher = None
        
        self.engine = None
        self.tasks = []
        
        # Rejection tracking for dashboard visibility
        self._rejection_counts = {}  # {reason: count}
        self._rejection_total = 0
        self._last_rejection_reason = ""
        self._signal_priority_symbols = set()  # Symbols boosted by slow strategies
        
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
            
            # Signal-Based Inventory Allocator
            self.signal_allocator = SignalAllocator(self.balance_manager)
            logger.info("✅ Signal Allocator initialized (HFT inventory management)")
            
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
            
            # ML Modules
            logger.info("\n🧠 Initializing ML Modules...")
            self.market_regime_detector = MarketRegimeDetector()
            logger.info("✅ Market Regime Detector initialized")
            self.ml_spread_predictor = MLSpreadPredictor()
            logger.info("✅ ML Spread Predictor initialized")
            self.fee_optimizer = FeeOptimizer()
            logger.info("✅ Fee Optimizer initialized")
            self.auto_parameter_optimizer = AutoParameterOptimizer()
            logger.info("✅ Auto Parameter Optimizer initialized")
            self.volatility_forecaster = VolatilityForecaster()
            logger.info("✅ Volatility Forecaster initialized")
            self.nn_predictor = NeuralNetworkPredictor()
            logger.info("✅ Neural Network Predictor initialized")
            self.rl_agent = ReinforcementLearningAgent()
            logger.info("✅ Reinforcement Learning Agent initialized")
            self.slippage_predictor = SlippagePredictor()
            logger.info("✅ Slippage Predictor initialized")
            self.auto_parameter_tuner = AutoParameterTuner()
            logger.info("✅ Auto Parameter Tuner initialized")
            self.pattern_recognition = PatternRecognition() if PatternRecognition else None
            logger.info(f"{'✅' if self.pattern_recognition else '⚠️'} Pattern Recognition {'initialized' if self.pattern_recognition else 'unavailable (numpy)'}")
            self.market_adaptive_strategy = MarketAdaptiveStrategy() if MarketAdaptiveStrategy else None
            logger.info(f"{'✅' if self.market_adaptive_strategy else '⚠️'} Market Adaptive Strategy {'initialized' if self.market_adaptive_strategy else 'unavailable (numpy)'}")
            self.ml_model_trainer = MLModelTrainer() if MLModelTrainer else None
            logger.info(f"{'✅' if self.ml_model_trainer else '⚠️'} ML Model Trainer {'initialized' if self.ml_model_trainer else 'unavailable (numpy)'}")
            
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
    
    def _on_mexc_task_done(self, task):
        """Callback when MEXC task completes (crash detection)."""
        try:
            exc = task.exception()
            if exc:
                logger.error(f"❌ MEXC task crashed: {type(exc).__name__}: {exc}")
                logger.error("   MEXC data will not be available. Restarting REST poll...")
                # Restart MEXC task with stdlib fallback
                mexc_exchanges = [e for e in getattr(self, 'exchanges', []) if isinstance(e, MEXC)]
                if mexc_exchanges:
                    mexc = mexc_exchanges[0]
                    mexc._ws_failed = True
                    self._mexc_task = asyncio.create_task(mexc._run_rest_poll_stdlib())
                    self._mexc_task.add_done_callback(self._on_mexc_task_done)
        except asyncio.CancelledError:
            pass  # Normal shutdown
        except asyncio.InvalidStateError:
            pass  # Task not done yet

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
            
            # MEXC uses async coroutine (not thread), start it as a task
            mexc = MEXC(self.store, symbols)
            self._mexc_task = asyncio.create_task(mexc.run())
            self._mexc_task.add_done_callback(self._on_mexc_task_done)
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
                    'lookback_period': 20,
                    'volume_threshold': 1.3,
                    'breakout_threshold': 0.001,
                    'min_touches': 2
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
            
            # Initialize Strategy Dispatcher (NEW: Manages all 14 strategies!)
            logger.info("\n🎯 Initializing Strategy Dispatcher (All 14 Strategies)...")
            self.strategy_dispatcher = StrategyDispatcher(self)
            logger.info("✅ Strategy Dispatcher initialized - ALL 14 STRATEGIES ACTIVE!")
            
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
            self.executor = executor
            
            # Wire executor into triangular engine
            if self.triangular_engine:
                self.triangular_engine.order_executor = executor
            self.engine = ArbitrageEngine(
                store=self.store,
                executor=executor,
                risk_manager=self.risk_manager,
                strategy_manager=self.strategy_manager,
                strategy_dispatcher=self.strategy_dispatcher,
                flash_crash_protector=self.flash_crash_protector,
                wash_trading_filter=self.wash_trading_filter,
                orderbook_imbalance_detector=self.orderbook_imbalance_detector,
                trade_journal=self.trade_journal,
                profit_attribution=self.profit_attribution,
                metrics_collector=self.metrics_collector,
                market_regime_detector=self.market_regime_detector,
                fee_optimizer=self.fee_optimizer,
                ml_spread_predictor=self.ml_spread_predictor,
                order_flow_tracker=self.order_flow_tracker,
                iceberg_detector=self.iceberg_detector,
                slippage_predictor=self.slippage_predictor,
                nn_predictor=self.nn_predictor,
                rl_agent=self.rl_agent,
                volatility_forecaster=self.volatility_forecaster,
                auto_parameter_tuner=self.auto_parameter_tuner,
                pattern_recognition=self.pattern_recognition,
                market_adaptive_strategy=self.market_adaptive_strategy,
                ml_model_trainer=self.ml_model_trainer,
                twap_engine=self.twap_engine,
                signal_allocator=getattr(self, 'signal_allocator', None),
                state_manager=self.state_manager
            )
            # Provide REST clients for JIT inventory acquisition in live mode
            self.engine._rest_clients = self.rest_clients
            logger.info("✅ Main Arbitrage Engine initialized with professional components + ML")
            
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
            
            # Inventory rebalance task (signal-based capital distribution)
            if hasattr(self, 'signal_allocator') and self.signal_allocator:
                rebalance_task = asyncio.create_task(self._rebalance_loop())
                self.tasks.append(rebalance_task)
                logger.info("✅ Signal-based inventory rebalance task started")
            
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
            
            # Periodic Telegram report task (every 4 hours + at midnight)
            if self.telegram_bot and self.state_manager:
                report_task = asyncio.create_task(self._periodic_report_loop())
                self.tasks.append(report_task)
                logger.info("✅ Periodic Telegram report task started (4h interval)")
            
            # Auto-rebalancer task
            if self.rebalancer:
                rebalance_task = asyncio.create_task(self.rebalancer.monitoring_loop())
                self.tasks.append(rebalance_task)
                logger.info("✅ Auto-rebalancer task started")
            
            # Triangular arbitrage task
            if self.triangular_engine:
                triangular_task = asyncio.create_task(self._triangular_scan_loop())
                self.tasks.append(triangular_task)
                logger.info("✅ Triangular arbitrage task started")
            
            # Strategy dispatcher slow scan task (scans 10 auxiliary strategies every 5 min)
            if self.strategy_dispatcher:
                strategy_task = asyncio.create_task(self._strategy_dispatcher_loop())
                self.tasks.append(strategy_task)
                logger.info("✅ Strategy dispatcher task started (14 strategies)")
            
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
        """Compact status dashboard — updates in-place, no jumping."""
        interval = settings.MONITOR_INTERVAL_SEC
        cycle = 0
        try:
            while True:
                await asyncio.sleep(interval)
                cycle += 1
                
                # Gather data
                snap = self.store.snapshot() if self.store else {}
                total_exchanges = sum(len(exmap) for exmap in snap.values()) if snap else 0
                active_symbols = len(snap) if snap else 0
                
                # Exchange connectivity
                exchanges_with_data = set()
                for exmap in snap.values():
                    exchanges_with_data.update(exmap.keys())
                
                # Executor stats
                executor = getattr(self.engine, 'executor', None) if self.engine else None
                exec_stats = executor.get_statistics() if executor else {}
                total_trades = exec_stats.get('total_orders', 0)
                total_profit = exec_stats.get('total_profit', 0.0)
                avg_roi = exec_stats.get('average_roi', 0.0)
                
                # Strategy dispatcher stats
                disp_stats = {}
                total_scans = 0
                total_opps = 0
                if self.strategy_dispatcher:
                    disp_stats = self.strategy_dispatcher.strategy_stats
                    total_scans = sum(s['calls'] for s in disp_stats.values())
                    total_opps = sum(s['opportunities'] for s in disp_stats.values())
                
                # Mode label
                mode = "🔵 DRY RUN" if settings.DRY_RUN else "🔴 LIVE"
                
                # Print compact dashboard
                print(f"\n{'='*70}")
                print(f" {mode} | Cycle #{cycle} | {active_symbols} symbols | {total_exchanges} connections")
                print(f"{'='*70}")
                
                # Connected exchanges with fee info
                all_exchanges = ['Bybit', 'KuCoin', 'HTX', 'MEXC', 'Binance']
                connected = [ex for ex in all_exchanges if ex in exchanges_with_data]
                disconnected = [ex for ex in all_exchanges if ex not in exchanges_with_data]
                # Show fee next to each connected exchange
                conn_parts = []
                for ex in connected:
                    fee = EXCHANGE_PARAMS.get(ex, {}).get('taker', 0)
                    conn_parts.append(f"{ex}({fee*100:g}%)")
                print(f" ✅ Connected: {', '.join(conn_parts) if conn_parts else 'none'}")
                if disconnected:
                    print(f" ❌ Disconnected: {', '.join(disconnected)}")
                
                # Strategies summary (compact)
                print(f"{'─'*70}")
                print(f" {'Strategy':<20} {'Scans':>8} {'Sigs':>6} {'Opps':>6} {'Trds':>6}")
                print(f"{'─'*70}")
                for name, stats in disp_stats.items():
                    calls = stats['calls']
                    signals = stats.get('signals', 0)
                    opps = stats['opportunities']
                    trades = stats.get('trades', 0)
                    print(f" {name:<20} {calls:>8} {signals:>6} {opps:>6} {trades:>6}")
                
                # Totals
                total_signals = sum(s.get('signals', 0) for s in disp_stats.values())
                total_trades_strat = sum(s.get('trades', 0) for s in disp_stats.values())
                print(f"{'─'*70}")
                print(f" {'TOTAL':<20} {total_scans:>8} {total_signals:>6} {total_opps:>6} {total_trades_strat:>6}")
                print(f"{'─'*70}")
                print(f" 💰 Trades: {total_trades} | Profit: ${total_profit:.4f} | Avg ROI: {avg_roi:.3f}%")
                
                # Profit reserve display
                if self.engine:
                    reserved = getattr(self.engine, '_reserved_profit', 0.0)
                    reinvested = getattr(self.engine, '_reinvested_profit', 0.0)
                    if total_profit > 0:
                        print(f" 💎 Reserve: ${reserved:.4f} (30% locked) | Reinvested: ${reinvested:.4f} (70%)")
                
                # Balance info — total portfolio value in USDT (all coins)
                if self.balance_manager:
                    total_bal = self.balance_manager.get_total_balance_usdt(self.engine.store if self.engine else None)
                    virt = " (virtual)" if settings.DRY_RUN else ""
                    print(f" 💵 Capital: ${total_bal:.2f} USDT equiv{virt}")
                
                # ML module status — comprehensive line
                ml_parts = []
                if self.market_regime_detector:
                    regimes = self.market_regime_detector.get_all_regimes()
                    if regimes:
                        from collections import Counter
                        rc = Counter(regimes.values())
                        top_regime = rc.most_common(1)[0][0] if rc else 'N/A'
                        ml_parts.append(f"Regime={top_regime}")
                    else:
                        ml_parts.append("Regime=N/A")
                if self.nn_predictor:
                    try:
                        cache = getattr(self.nn_predictor, 'prediction_cache', {})
                        if cache:
                            last_val = list(cache.values())[-1][1]
                            ml_parts.append(f"NN conf={last_val:.2f}")
                        else:
                            ml_parts.append("NN conf=N/A")
                    except Exception:
                        ml_parts.append("NN conf=N/A")
                if self.rl_agent:
                    try:
                        eps = getattr(self.rl_agent, 'epsilon', 0)
                        ml_parts.append(f"RL ε={eps:.2f}")
                    except Exception:
                        pass
                if self.ml_spread_predictor:
                    ewma_vals = getattr(self.ml_spread_predictor, 'ewma_values', {})
                    if ewma_vals:
                        avg_ewma = sum(ewma_vals.values()) / len(ewma_vals)
                        ml_parts.append(f"Spread EWMA={avg_ewma*100:.2f}%")
                    else:
                        ml_parts.append("Spread EWMA=learning")
                if self.volatility_forecaster:
                    try:
                        vol_regimes = {s: self.volatility_forecaster.get_regime(s)
                                       for s in list(getattr(self.volatility_forecaster, 'ewma_var', {}).keys())[:3]}
                        if vol_regimes:
                            top_vol = next(iter(vol_regimes.values()), 'N/A')
                            ml_parts.append(f"Vol={top_vol}")
                    except Exception:
                        pass
                if ml_parts:
                    print(f" 🧠 ML: {' | '.join(ml_parts)}")
                
                # Engine analytics: best spread seen THIS cycle + near-miss tracking
                if self.engine:
                    best_spread = getattr(self.engine, '_best_spread_pct', 0)
                    best_info = getattr(self.engine, '_best_spread_info', '')
                    best_fees = getattr(self.engine, '_best_spread_fees_pct', 0)
                    near_misses = getattr(self.engine, '_near_miss_count', 0)
                    total_analyzed = getattr(self.engine, '_total_pairs_analyzed', 0)
                    if best_spread > 0:
                        gap = best_fees - best_spread
                        pct_of_fees = (best_spread / best_fees * 100) if best_fees > 0 else 0
                        print(f" 📊 Best spread: {best_spread:.4f}% ({pct_of_fees:.0f}% of {best_fees:.3f}% fees, gap={gap:.4f}%) | {best_info}")
                    if near_misses > 0 or total_analyzed > 0:
                        print(f" 🔍 Near-misses: {near_misses} | Pairs analyzed: {total_analyzed}")
                    # Reset per-cycle metrics so dashboard shows CURRENT state
                    self.engine._best_spread_pct = 0.0
                    self.engine._best_spread_info = ""
                    self.engine._best_spread_fees_pct = 0.0
                
                # Rejection summary — shows WHY trades don't happen
                if self._rejection_total > 0:
                    top_reason = max(self._rejection_counts, key=self._rejection_counts.get) if self._rejection_counts else "N/A"
                    top_count = self._rejection_counts.get(top_reason, 0)
                    priority = ", ".join(sorted(self._signal_priority_symbols)[:5]) if self._signal_priority_symbols else "none"
                    print(f" ⛔ Rejected: {self._rejection_total} trades ({top_reason}: {top_count}) | Priority symbols: {priority}")
                
                print(f"{'='*70}")
                
                # Every 1000 cycles, print detailed summary
                if cycle % 1000 == 0:
                    print(f"\n{'*'*70}")
                    print(f"  📊 MILESTONE: {cycle} CYCLES COMPLETED")
                    print(f"{'*'*70}")
                    if executor:
                        executor.print_statistics()
                    if self.strategy_dispatcher:
                        self.strategy_dispatcher.print_stats()
                    if self.risk_manager:
                        logger.info(f"Risk status: Daily P&L: ${self.risk_manager.daily_pnl:.2f}")
                    print(f"{'*'*70}\n")
                
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
                    # Update balance in performance tracker (total portfolio in USDT)
                    price_store = self.engine.store if self.engine else None
                    total_balance = self.balance_manager.get_total_balance_usdt(price_store)
                    if total_balance <= 0:
                        total_balance = self.balance_manager.get_total_balance('USDT')
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
                
                # Log signal allocator status (inventory recommendations)
                if hasattr(self, 'signal_allocator') and self.signal_allocator:
                    summary = self.signal_allocator.get_summary()
                    if summary['total_signals'] > 0:
                        top = summary.get('top_symbols', [])[:3]
                        if top:
                            top_str = ', '.join(f"{t['symbol']}({t['signals']})" for t in top)
                            logger.info(f"📦 Inventory signals: {summary['total_signals']} total | Top: {top_str}")
                
        except asyncio.CancelledError:
            return
    
    async def _rebalance_loop(self):
        """Periodic + reactive inventory rebalance.
        
        Two modes:
        1. PERIODIC (every 60s): Check if inventory needs rebalancing
        2. REACTIVE (instant): When 2+ missed trades for same coin in 60s,
           immediately pre-position that coin
        
        In DRY RUN: updates virtual balances.
        In LIVE: places real market buy/sell orders.
        """
        INITIAL_POLL_INTERVAL = 10   # Check every 10s while searching for first coin
        NORMAL_REBALANCE_INTERVAL = 300  # Check every 5 min after first coin positioned
        
        try:
            logger.info("🔄 Inventory rebalance loop started — UNLIMITED time to find first coin (polling every 10s)")
            first_coin_found = False
            
            while True:
                try:
                    price_store = self.engine.store if self.engine else None
                    
                    # Check for URGENT rebalance (missed opportunities)
                    urgent = (
                        self.signal_allocator 
                        and self.signal_allocator.needs_urgent_rebalance()
                    )
                    
                    # Normal rebalance if we have enough signals, OR urgent
                    has_signals = (
                        self.signal_allocator 
                        and self.signal_allocator.has_sufficient_signals(30)
                    )
                    
                    if has_signals or urgent:
                        allocation = self.signal_allocator.get_allocation()
                        if allocation:
                            mode = "🔥 URGENT" if urgent else ("🎯 FIRST COIN" if not first_coin_found else "🔄 Periodic")
                            logger.info(
                                f"{mode} rebalance — "
                                f"{len(allocation)} target coins"
                            )
                            
                            orders = await self.signal_allocator.execute_rebalance(
                                rest_clients=getattr(self, 'rest_clients', None),
                                price_store=price_store,
                            )
                            
                            if orders:
                                for order in orders:
                                    logger.info(
                                        f"  📦 {order['side'].upper()} {order.get('qty', 0):.6g} "
                                        f"{order['symbol']} on {order['exchange']} "
                                        f"(${order['amount_usdt']:.2f}) — {order['reason']}"
                                    )
                                if not first_coin_found:
                                    first_coin_found = True
                                    logger.info("✅ First coin positioned! Switching to normal 5-min rebalance interval")
                            else:
                                logger.debug("Rebalance: no orders needed (inventory balanced)")
                    elif not first_coin_found:
                        # Still searching for first coin — log progress
                        # _signals is a flat List[SignalRecord], not a dict
                        total_signals = sum(
                            1 for s in self.signal_allocator._signals if s.roi_pct > 0
                        ) if self.signal_allocator else 0
                        logger.info(f"🔍 Searching for first coin... {total_signals} positive-ROI signals so far (need 30+ for one coin)")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Rebalance error: {e}")
                
                # Fast polling while searching, slow polling after first coin found
                interval = NORMAL_REBALANCE_INTERVAL if first_coin_found else INITIAL_POLL_INTERVAL
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            return
    
    async def _triangular_scan_loop(self):
        """Background task for triangular arbitrage scanning."""
        try:
            await asyncio.sleep(5)  # Wait for price data
            while True:
                try:
                    opps = self.triangular_engine.scan_opportunities()
                    if opps:
                        for opp in opps:
                            logger.info(
                                f"🔺 TRI: {opp['route']} on {opp['exchange']} "
                                f"profit={opp['profit_pct']:.3f}%"
                            )
                            if self.executor:
                                await self.triangular_engine.execute_opportunity(opp)
                            if self.strategy_dispatcher:
                                self.strategy_dispatcher.strategy_stats['TRIANGULAR']['opportunities'] += 1
                except Exception as e:
                    logger.warning(f"Triangular scan error: {e}")
                await asyncio.sleep(2)  # Scan every 2 seconds
        except asyncio.CancelledError:
            logger.info("Triangular scan loop cancelled")

    async def _periodic_report_loop(self):
        """Send periodic P&L reports via Telegram (every 4 hours)."""
        REPORT_INTERVAL = 4 * 3600  # 4 hours
        await asyncio.sleep(300)  # Wait 5 min before first report
        
        try:
            while True:
                await asyncio.sleep(REPORT_INTERVAL)
                if self.state_manager and self.telegram_bot:
                    stats = self.state_manager.get_statistics()
                    # Add top/losing symbols
                    top_syms = self.state_manager.get_top_symbols(3)
                    losing_syms = self.state_manager.get_losing_symbols()
                    
                    top_str = ', '.join(f"{s}: ${d['pnl']:.4f}" for s, d in top_syms) if top_syms else 'None yet'
                    lose_str = ', '.join(f"{s}: ${d['pnl']:.4f}" for s, d in losing_syms[:3]) if losing_syms else 'None'
                    
                    stats['top_symbols'] = top_str
                    stats['losing_symbols'] = lose_str
                    stats['win_rate'] = 0
                    
                    total_trades = stats.get('trades_today', 0)
                    if total_trades > 0:
                        sym_pnl = self.state_manager.get_symbol_pnl()
                        total_wins = sum(d.get('wins', 0) for d in sym_pnl.values())
                        total_all = sum(d.get('trades', 0) for d in sym_pnl.values())
                        stats['win_rate'] = (total_wins / total_all * 100) if total_all > 0 else 0
                    
                    await self.telegram_bot.notify_daily_report(stats)
        except asyncio.CancelledError:
            logger.info("Periodic report loop cancelled")

    async def _strategy_dispatcher_loop(self):
        """Background task for running strategy dispatcher scans.
        
        Scans all 14 strategies and routes executable opportunities
        to OrderExecutor for trade execution (dry-run or live).
        """
        try:
            while True:
                all_opps = []
                
                # Fast scan: TRIANGULAR, SMART_ORDER, VOLATILITY
                # (CROSS_EXCHANGE is handled by ArbitrageEngine.run())
                if self.strategy_dispatcher:
                    fast_opps = await self.strategy_dispatcher.scan_fast()
                    if fast_opps:
                        all_opps.extend(fast_opps)
                
                # Slow scan: 10 auxiliary strategies (every 60s)
                if self.strategy_dispatcher and self.strategy_dispatcher.should_scan_slow():
                    slow_opps = await self.strategy_dispatcher.scan_slow()
                    if slow_opps:
                        all_opps.extend(slow_opps)
                        # Boost: slow strategy signals push symbols into engine's
                        # priority queue so they get scanned on the next fast cycle
                        if self.engine and hasattr(self.engine, 'updated_symbols'):
                            for opp in slow_opps:
                                sym = opp.get('symbol', '')
                                if '/' in sym:
                                    sym = sym.split('/')[0]
                                if sym:
                                    self.engine.updated_symbols.add(sym)
                
                # Execute opportunities that have actionable trade data
                if all_opps and hasattr(self, 'engine') and self.engine:
                    executable = [o for o in all_opps if self._is_executable(o)]
                    if executable:
                        logger.info(f"🎯 Strategies found {len(executable)} executable opportunities (of {len(all_opps)} signals)")
                        for opp in executable:
                            trade_info = self._build_trade_from_signal(opp)
                            if trade_info:
                                # Risk check
                                if self.risk_manager:
                                    can_trade, reason = self.risk_manager.check_can_trade(trade_info)
                                    if not can_trade:
                                        logger.debug(f"Risk manager blocked {opp['strategy']}: {reason}")
                                        # Alert on risk limit hits (pauses)
                                        if self.telegram_bot and 'paused' in str(reason).lower():
                                            try:
                                                asyncio.create_task(self.telegram_bot.notify_risk_limit_hit(
                                                    opp['strategy'], reason))
                                            except Exception:
                                                pass
                                        continue
                                # Execute via OrderExecutor
                                result = await self.engine.executor.execute_arbitrage(trade_info)
                                if result.get('status') in ('simulated', 'success'):
                                    logger.info(f"✅ {opp['strategy']} trade executed: {trade_info['symbol']} ${trade_info.get('net', 0):.4f}")
                                    # Record trade in dispatcher stats
                                    if self.strategy_dispatcher:
                                        self.strategy_dispatcher.strategy_stats[opp['strategy']]['trades'] += 1
                                    # Record to strategy manager
                                    if self.strategy_manager:
                                        self.strategy_manager.record_trade(
                                            strategy_name=opp['strategy'],
                                            success=True,
                                            profit=trade_info.get('net', 0),
                                            execution_time=0
                                        )
                                    # Record to signal allocator for inventory management
                                    if hasattr(self, 'signal_allocator') and self.signal_allocator:
                                        self.signal_allocator.record_trade(
                                            symbol=trade_info['symbol'],
                                            strategy=opp['strategy'],
                                            exchange=trade_info.get('buy_ex', ''),
                                            roi_pct=trade_info.get('roi_pct', 0)
                                        )
                                    # Record to state manager (trade journal + per-symbol P&L)
                                    if self.state_manager:
                                        trade_info['strategy'] = opp['strategy']
                                        self.state_manager.record_trade_detail(trade_info)
                                        self.state_manager.add_to_daily_pnl(trade_info.get('net', 0))
                                        self.state_manager.increment_trades()
                                    # Telegram notification
                                    if self.telegram_bot:
                                        try:
                                            asyncio.create_task(self.telegram_bot.notify_trade_executed(trade_info))
                                        except Exception:
                                            pass
                            else:
                                # Signal didn't produce a trade but still useful for allocation
                                if hasattr(self, 'signal_allocator') and self.signal_allocator:
                                    sym = opp.get('symbol', '')
                                    if '/' in sym:
                                        sym = sym.split('/')[0]
                                    if sym:
                                        self.signal_allocator.record_signal(
                                            symbol=sym,
                                            strategy=opp['strategy'],
                                            exchange=opp.get('data', {}).get('exchange', ''),
                                            roi_pct=opp.get('data', {}).get('roi_pct', 0)
                                        )
                
                await asyncio.sleep(settings.SCAN_INTERVAL_SEC)
                
        except asyncio.CancelledError:
            return
    
    def _is_executable(self, opp: dict) -> bool:
        """Check if a strategy signal has enough data to execute a trade."""
        strategy = opp.get('strategy', '')
        # These strategies produce actionable cross-exchange trades
        if strategy in ('TRIANGULAR', 'FUNDING_RATE', 'INDEX_ARB'):
            return True
        # SMART_ORDER: wide spread = profitable cross-exchange opportunity
        if strategy == 'SMART_ORDER' and opp.get('data', {}).get('spread_pct', 0) > 0:
            return True
        # VOLATILITY_ARB: spread width difference between exchanges
        if strategy == 'VOLATILITY_ARB' and opp.get('data', {}):
            return True
        # MARKET_MAKING signals with spread data can execute
        if strategy == 'MARKET_MAKING' and opp.get('data', {}).get('spread_pct', 0) > 0:
            return True
        # DCA buy signals
        if strategy == 'DCA' and opp.get('data', {}).get('dip_pct', 0) > 0:
            return True
        # PAIRS_TRADING z-score signals
        if strategy == 'PAIRS_TRADING' and abs(opp.get('data', {}).get('z_score', 0)) > 0:
            return True
        # SPREAD_BETTING z-score signals
        if strategy == 'SPREAD_BETTING' and abs(opp.get('data', {}).get('z_score', 0)) > 0:
            return True
        # MOMENTUM with strong signal
        if strategy == 'MOMENTUM' and opp.get('data', {}).get('strength', 0) > 0.6:
            return True
        # BREAKOUT detected
        if strategy == 'BREAKOUT' and opp.get('data', {}):
            return True
        # VOLATILITY: high volatility = spread opportunities
        if strategy == 'VOLATILITY' and opp.get('data', {}).get('volatility_pct', 0) > 0:
            return True
        # GRID_TRADING: price deviation from center
        if strategy == 'GRID_TRADING' and opp.get('data', {}).get('deviation_pct', 0) > 0:
            return True
        return False
    
    def _build_trade_from_signal(self, opp: dict) -> dict:
        """Convert a strategy signal into an executable trade dict.
        
        Uses PriceStore real-time data to find the best buy/sell exchange
        pair that aligns with the strategy signal.
        
        When a strategy produces a HIGH-CONFIDENCE signal (z-score > 2.0,
        RSI extreme, etc.), the required ROI threshold is reduced by up to
        50% because the statistical edge combines with the spread opportunity.
        """
        strategy = opp.get('strategy', '')
        symbol = opp.get('symbol', 'BTC-USDT')
        data = opp.get('data', {})
        
        # For pair strategies, use the first symbol
        if '/' in symbol:
            symbol = symbol.split('/')[0]
        
        store = getattr(self, 'store', None)
        if not store:
            return None
        
        snap = store.snapshot()
        exmap = snap.get(symbol, {})
        if len(exmap) < 2:
            logger.debug(f"  ↳ {strategy} {symbol}: only {len(exmap)} exchange(s), need ≥2")
            return None
        
        # Find best buy (lowest ask) and sell (highest bid) exchanges
        best_buy_ex, best_buy_price = None, float('inf')
        best_sell_ex, best_sell_price = None, 0.0
        
        for ex, rec in exmap.items():
            ask = rec.get('ask')
            bid = rec.get('bid')
            if ask and ask < best_buy_price:
                best_buy_price = ask
                best_buy_ex = ex
            if bid and bid > best_sell_price:
                best_sell_price = bid
                best_sell_ex = ex
        
        # Use exchange hint from strategies like FUNDING_RATE and INDEX_ARB:
        # If strategy says exchange X has a premium (high price), sell there.
        # If exchange X has a discount (low price), buy there.
        hint_ex = data.get('exchange', '')
        hint_dev = data.get('deviation_pct', 0)
        if hint_ex and hint_dev != 0 and hint_ex in exmap:
            rec = exmap[hint_ex]
            if hint_dev > 0 and rec.get('bid'):
                # Premium on this exchange → sell here, buy elsewhere
                best_sell_ex = hint_ex
                best_sell_price = rec['bid']
                # Find cheapest other exchange to buy
                best_buy_ex, best_buy_price = None, float('inf')
                for ex, r in exmap.items():
                    if ex != hint_ex and r.get('ask') and r['ask'] < best_buy_price:
                        best_buy_price = r['ask']
                        best_buy_ex = ex
            elif hint_dev < 0 and rec.get('ask'):
                # Discount on this exchange → buy here, sell elsewhere
                best_buy_ex = hint_ex
                best_buy_price = rec['ask']
                # Find most expensive other exchange to sell
                best_sell_ex, best_sell_price = None, 0.0
                for ex, r in exmap.items():
                    if ex != hint_ex and r.get('bid') and r['bid'] > best_sell_price:
                        best_sell_price = r['bid']
                        best_sell_ex = ex
        
        if not best_buy_ex or not best_sell_ex or best_buy_ex == best_sell_ex:
            self._track_rejection("same_exchange")
            return None
        
        # Calculate profit with real prices and fees
        from core.exchange_config import EXCHANGE_PARAMS
        buy_fee = EXCHANGE_PARAMS.get(best_buy_ex, {}).get('taker', 0.001)
        sell_fee = EXCHANGE_PARAMS.get(best_sell_ex, {}).get('taker', 0.001)
        
        # Calculate max trade size from exposure limit (scales with capital)
        qty = settings.MAX_EXPOSURE_USDT / best_buy_price if best_buy_price > 0 else 0
        if qty <= 0:
            return None
        
        invested = best_buy_price * qty
        fees = invested * buy_fee + (best_sell_price * qty) * sell_fee
        gross = (best_sell_price - best_buy_price) * qty
        net = gross - fees
        roi_pct = (net / invested) * 100 if invested > 0 else 0
        
        # Signal confidence reduces required ROI threshold:
        # High-confidence signals (z>2.0, RSI extreme) add statistical
        # edge on top of the spread, so we lower the bar by up to 80%.
        confidence = self._signal_confidence(strategy, data)
        min_roi = settings.MIN_NET_ROI_PCT * (1.0 - 0.8 * confidence)
        
        # Only return if profitable after fees (with confidence-adjusted threshold)
        if net <= 0 or roi_pct < min_roi:
            spread_pct = ((best_sell_price - best_buy_price) / best_buy_price) * 100
            fee_pct = (buy_fee + sell_fee) * 100
            gap = fee_pct - spread_pct
            reason = f"spread<fees ({spread_pct:.3f}%<{fee_pct:.2f}%, gap={gap:.3f}%)"
            self._track_rejection(reason, strategy, symbol, best_buy_ex, best_sell_ex, spread_pct, fee_pct)
            return None
        
        return {
            'symbol': symbol,
            'buy_ex': best_buy_ex,
            'sell_ex': best_sell_ex,
            'qty': qty,
            'buy_avg': best_buy_price,
            'sell_avg': best_sell_price,
            'gross': gross,
            'fees': fees,
            'net': net,
            'roi_pct': roi_pct,
            'strategy': strategy,
        }
    
    def _signal_confidence(self, strategy: str, data: dict) -> float:
        """Calculate signal confidence [0.0 - 1.0] from strategy-specific metrics.
        
        Higher confidence = lower ROI threshold needed for execution.
        Returns 0.0 for strategies without statistical edge (pure spread).
        """
        if strategy in ('PAIRS_TRADING', 'SPREAD_BETTING'):
            # z-score > 2.0 = high confidence, > 3.0 = very high
            z = abs(data.get('z_score', 0))
            return min(z / 4.0, 1.0) if z > 2.0 else 0.0  # Raised from 1.5 to match scanner
        elif strategy == 'MOMENTUM':
            # RSI < 25 or > 75 = high confidence (extreme overbought/oversold)
            rsi = data.get('rsi', 50)
            # Normalized distance from RSI=50, range [0.0, 1.0]
            extremity = min(abs(rsi - 50) / 50.0, 1.0)
            return extremity if extremity > 0.4 else 0.0
        elif strategy == 'FUNDING_RATE':
            # Scanner sends 'deviation_pct'; accept both keys for robustness
            premium = abs(data.get('deviation_pct', data.get('premium_pct', 0)))
            return min(premium / 1.0, 1.0) if premium > 0.2 else 0.0
        elif strategy == 'INDEX_ARB':
            deviation = abs(data.get('deviation_pct', 0))
            return min(deviation / 0.5, 1.0) if deviation > 0.1 else 0.0
        elif strategy == 'VOLATILITY_ARB':
            return 0.3  # Moderate base confidence for vol differences
        elif strategy == 'DCA':
            dip = data.get('dip_pct', 0)
            return min(dip / 5.0, 1.0) if dip > 1.0 else 0.0
        elif strategy == 'BREAKOUT':
            return 0.5  # Breakout signals have moderate confidence
        elif strategy == 'MARKET_MAKING':
            spread = data.get('spread_pct', 0)
            return min(spread / 1.0, 1.0) if spread > 0.1 else 0.0
        elif strategy in ('SMART_ORDER', 'VOLATILITY'):
            return 0.3  # Moderate confidence for market condition signals
        elif strategy == 'GRID_TRADING':
            # Higher deviation = higher confidence
            dev = data.get('deviation_pct', 0)
            return min(dev / 2.0, 1.0) if dev > 0.3 else 0.0  # Only >0.3% deviation
        # Pure spread strategies: no additional statistical edge
        return 0.0
    
    def _track_rejection(self, reason: str, strategy: str = "", symbol: str = "",
                         buy_ex: str = "", sell_ex: str = "",
                         spread_pct: float = 0, fee_pct: float = 0):
        """Track trade rejections for dashboard visibility."""
        self._rejection_total += 1
        # Bucket by general reason type
        bucket = "spread<fees" if "spread<fees" in reason else reason
        self._rejection_counts[bucket] = self._rejection_counts.get(bucket, 0) + 1
        self._last_rejection_reason = reason
        
        # Log every 50th rejection at INFO so user sees it
        if self._rejection_total % 50 == 1:
            logger.info(
                f"📊 Rejection #{self._rejection_total}: {strategy} {symbol} "
                f"{buy_ex}→{sell_ex} spread={spread_pct:.3f}% < fees={fee_pct:.2f}%"
            )
        
        # If a slow strategy signal gets rejected, it's still useful:
        # add the symbol to the priority scan set so ArbitrageEngine
        # scans it more frequently (slow strategy signals = statistical edge,
        # just waiting for spread to widen enough)
        if strategy in ('PAIRS_TRADING', 'MOMENTUM', 'DCA', 'FUNDING_RATE',
                        'INDEX_ARB', 'VOLATILITY_ARB', 'SPREAD_BETTING', 'BREAKOUT'):
            self._signal_priority_symbols.add(symbol)
    
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
            # Print strategy dispatcher statistics
            if self.strategy_dispatcher:
                self.strategy_dispatcher.print_stats()
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
        
        # Cancel MEXC asyncio task
        if self._mexc_task and not self._mexc_task.done():
            self._mexc_task.cancel()
            try:
                await self._mexc_task
            except asyncio.CancelledError:
                pass
        
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
    """Main entry point with auto-restart on crash."""
    MAX_RESTARTS = 5
    RESTART_DELAYS = [5, 15, 30, 60, 120]  # Exponential backoff
    
    for attempt in range(MAX_RESTARTS + 1):
        bot = IntegratedArbitrageBot()
        
        try:
            # Initialize all components
            success = await bot.initialize()
            if not success:
                logger.error("Initialization failed, exiting...")
                return 1
            
            # Run the bot
            await bot.run()
            return 0  # Clean exit
            
        except KeyboardInterrupt:
            logger.info("\n⚠️  KeyboardInterrupt received")
            await bot.shutdown()
            return 0
        except Exception as e:
            logger.exception(f"❌ Fatal error (attempt {attempt + 1}/{MAX_RESTARTS + 1}): {e}")
            
            # Record crash in state manager
            if bot.state_manager:
                bot.state_manager.record_crash()
            
            await bot.shutdown()
            
            if attempt < MAX_RESTARTS:
                delay = RESTART_DELAYS[min(attempt, len(RESTART_DELAYS) - 1)]
                logger.info(f"🔄 Auto-restarting in {delay}s (attempt {attempt + 2}/{MAX_RESTARTS + 1})...")
                
                # Send Telegram alert about restart
                if bot.telegram_bot:
                    try:
                        await bot.telegram_bot.send_message(
                            f"🔄 Bot crashed: {str(e)[:100]}\nRestarting in {delay}s (attempt {attempt + 2})")
                    except Exception:
                        pass
                
                await asyncio.sleep(delay)
            else:
                logger.error(f"❌ Max restarts ({MAX_RESTARTS}) exceeded. Giving up.")
                if bot.telegram_bot:
                    try:
                        await bot.telegram_bot.send_message(
                            f"🔴 Bot stopped after {MAX_RESTARTS} restart attempts.\nLast error: {str(e)[:150]}")
                    except Exception:
                        pass
                return 1


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Arbitrage Bot - Cryptocurrency Arbitrage Trading')
    parser.add_argument('--mode', 
                       choices=['dry-run', 'real'], 
                       default='dry-run',
                       help='Trading mode: dry-run (safe simulation) or real (live trading with real money)')
    args = parser.parse_args()
    
    # Override DRY_RUN setting based on CLI argument
    import settings
    if args.mode == 'real':
        settings.DRY_RUN = False
        print("🔴 REAL TRADING MODE - Using real money! Be careful!")
    else:
        settings.DRY_RUN = True
        print("🔵 DRY RUN MODE - Safe simulation (no real trades)")
    
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
