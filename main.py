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
import time
from collections import defaultdict
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
from core.capital_manager import CapitalManager  # Engine 2.0: capital-level mode selection
from core.semi_hft_engine import SemiHFTEngine  # Semi-HFT: professional execution layer

# Professional Infrastructure
from infrastructure.health_monitor import HealthMonitor
from infrastructure.alert_manager import AlertManager
from infrastructure.rate_limiter import RateLimiter
from infrastructure.circuit_breaker_enhanced import CircuitBreakerEnhanced
from infrastructure.metrics_collector import MetricsCollector

# Professional Analytics (optional — require numpy)
try:
    from analytics.trade_journal import TradeJournal
    from analytics.performance_tracker import PerformanceTracker
    from analytics.profit_attribution import ProfitAttributionAnalyzer
    from analytics.risk_analytics import RiskAnalytics
    from analytics.backtest_engine import BacktestEngine
    from analytics.market_intelligence import MarketIntelligence
    from analytics.realtime_analytics import RealtimeAnalytics
    from analytics.correlation_analyzer import CorrelationAnalyzer
    from analytics.custom_dashboard import CustomDashboard
except (ImportError, ModuleNotFoundError):
    TradeJournal = PerformanceTracker = ProfitAttributionAnalyzer = None
    RiskAnalytics = BacktestEngine = MarketIntelligence = None
    RealtimeAnalytics = CorrelationAnalyzer = CustomDashboard = None

# Professional Features (optional — require numpy)
try:
    from professional_features.flash_crash_protector import FlashCrashProtector
    from professional_features.wash_trading_filter import WashTradingFilter
    from professional_features.orderbook_imbalance_detector import OrderBookImbalanceDetector
except (ImportError, ModuleNotFoundError):
    FlashCrashProtector = WashTradingFilter = OrderBookImbalanceDetector = None

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

# Professional Execution (optional — require numpy)
try:
    from professional_features.twap_engine import TWAPEngine
    from professional_features.vwap_engine import VWAPEngine
    from professional_features.iceberg_order_detector import IcebergOrderDetector
    from professional_features.order_flow_tracker import OrderFlowTracker
except (ImportError, ModuleNotFoundError):
    TWAPEngine = VWAPEngine = IcebergOrderDetector = OrderFlowTracker = None

# ML modules (optional — require numpy/pandas)
try:
    from ml.market_regime_detector import MarketRegimeDetector
except (ImportError, ModuleNotFoundError):
    MarketRegimeDetector = None
try:
    from ml.ml_spread_predictor import MLSpreadPredictor
except (ImportError, ModuleNotFoundError):
    MLSpreadPredictor = None
try:
    from ml.auto_parameter_optimizer import AutoParameterOptimizer
except (ImportError, ModuleNotFoundError):
    AutoParameterOptimizer = None
try:
    from ml.volatility_forecaster import VolatilityForecaster
except (ImportError, ModuleNotFoundError):
    VolatilityForecaster = None
try:
    from ml.neural_network_predictor import NeuralNetworkPredictor
except (ImportError, ModuleNotFoundError):
    NeuralNetworkPredictor = None
try:
    from ml.reinforcement_learning_agent import ReinforcementLearningAgent
except (ImportError, ModuleNotFoundError):
    ReinforcementLearningAgent = None
try:
    from ml.slippage_predictor import SlippagePredictor
except (ImportError, ModuleNotFoundError):
    SlippagePredictor = None
try:
    from ml.auto_parameter_tuner import AutoParameterTuner
except (ImportError, ModuleNotFoundError):
    AutoParameterTuner = None
try:
    from ml.pattern_recognition import PatternRecognition
except (ImportError, ModuleNotFoundError):
    PatternRecognition = None
try:
    from ml.market_adaptive_strategy import MarketAdaptiveStrategy
except (ImportError, ModuleNotFoundError):
    MarketAdaptiveStrategy = None
try:
    from ml.ml_model_trainer import MLModelTrainer
except (ImportError, ModuleNotFoundError):
    MLModelTrainer = None

# Fee optimization (optional — requires numpy)
try:
    from core.fee_optimizer import FeeOptimizer
except (ImportError, ModuleNotFoundError):
    FeeOptimizer = None

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


class _DashboardErrorCapture(logging.Handler):
    """Captures ERROR-level log messages for the static dashboard display."""
    MAX_ERRORS = 10

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.errors = []

    def emit(self, record):
        msg = self.format(record)
        self.errors.append(msg)
        if len(self.errors) > self.MAX_ERRORS:
            self.errors = self.errors[-self.MAX_ERRORS:]


_dashboard_error_handler = _DashboardErrorCapture()
_dashboard_error_handler.setFormatter(logging.Formatter('%(message)s'))
logging.getLogger().addHandler(_dashboard_error_handler)

# ANSI escape for static dashboard (clear screen + cursor to top-left)
ANSI_CLEAR_AND_HOME = '\033[2J\033[H'

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
        
        # Engine 2.0: Capital Manager
        self.capital_manager = None
        
        self.engine = None
        self.tasks = []
        
        # Rejection tracking for dashboard visibility
        self._rejection_counts = {}  # {reason: count}
        self._rejection_total = 0
        self._last_rejection_reason = ""
        self._signal_priority_symbols = set()  # Symbols boosted by slow strategies
        self._dashboard_errors = []  # Recent errors for dashboard display
        
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
        
        # Phase 7: Seed HFT latency data (MUST be after Phase 6 which creates SemiHFTEngine)
        logger.info("\n📡 Phase 7: Seeding exchange latency data...")
        await self._seed_hft_latency()
        
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
            
            # Sync server time for ALL clients (prevents "Timestamp outside recvWindow" errors)
            if self.rest_clients:
                logger.info("🕐 Syncing server time for all exchanges...")
                sync_tasks = []
                client_names = []
                for name, client in self.rest_clients.items():
                    if hasattr(client, 'sync_server_time'):
                        sync_tasks.append(client.sync_server_time())
                        client_names.append(name)
                if sync_tasks:
                    results = await asyncio.gather(*sync_tasks, return_exceptions=True)
                    for name, result in zip(client_names, results):
                        if isinstance(result, Exception):
                            logger.warning(f"⚠️ {name} time sync failed: {result}")
                logger.info("✅ Server time sync complete")
            
            # NOTE: HFT latency seeding moved to Phase 7 (_seed_hft_latency)
            # because SemiHFTEngine is created in Phase 6, AFTER this method runs.
            
        except Exception as e:
            logger.error(f"❌ Error initializing REST clients: {e}")
            raise
    
    async def _seed_hft_latency(self):
        """Measure REST client RTT at startup — seeds HFT with REAL latency data.
        
        MUST run AFTER Phase 6 (SemiHFTEngine creation).
        Without this, HFT dashboard shows "no data" and exchange filtering
        uses default 200ms for all exchanges → no intelligent selection.
        Also seeds ArbitrageEngine's _exchange_latency_ms for threshold calculations.
        """
        if not hasattr(self, 'semi_hft_engine') or not self.semi_hft_engine or not self.rest_clients:
            logger.info("ℹ️ HFT latency seeding skipped (no HFT engine or REST clients)")
            return
        
        logger.info("📡 Measuring exchange latency (REST ping)...")
        for name, client in self.rest_clients.items():
            try:
                t0 = time.time()
                # Use sync_server_time — all 5 clients support it, no args needed
                await client.sync_server_time()
                rtt_ms = (time.time() - t0) * 1000
                self.semi_hft_engine.record_latency(name, rtt_ms)
                # Also seed ArbitrageEngine's latency for threshold calculations
                if self.engine:
                    self.engine.update_exchange_latency(name, rtt_ms)
                logger.info(f"  📡 {name}: {rtt_ms:.0f}ms RTT")
            except Exception as e:
                # Don't record fatal latency on startup failure — just log and skip
                logger.warning(f"  ⚠️ {name}: ping failed ({e}), will use default latency")
        
        all_names = list(self.rest_clients.keys())
        top = self.semi_hft_engine.get_top_exchanges(all_names, n=3)
        logger.info(f"🏆 Top exchanges by latency: {', '.join(top)}")
    
    async def _recover_pending_orders(self):
        """Process orphaned pending orders from a previous session (crash recovery)."""
        STALE_ORDER_TIMEOUT_SEC = 300  # 5 minutes — orders older than this are considered stale
        
        if not self.state_manager or not self.rest_clients:
            return
        
        pending = self.state_manager.get_pending_orders()
        if not pending:
            return
        
        logger.warning(f"🔄 RECOVERY: Found {len(pending)} pending orders from previous session")
        
        for order in list(pending):
            exchange = order.get('exchange', '')
            symbol = order.get('symbol', '')
            order_id = order.get('order_id', '')
            side = order.get('side', '')
            age_sec = time.time() - order.get('added_at', 0)
            
            client = self.rest_clients.get(exchange)
            if not client:
                logger.warning(f"   ⚠️ No client for {exchange}, removing stale order {order_id}")
                self.state_manager.remove_pending_order(order_id)
                continue
            
            try:
                # Try to check order status
                status = await client.get_order_status(symbol, order_id)
                if isinstance(status, Exception):
                    logger.warning(f"   ⚠️ Cannot check order {order_id} on {exchange}: {status}")
                    # If order is very old, it's likely dead — remove
                    if age_sec > STALE_ORDER_TIMEOUT_SEC:
                        logger.info(f"   🗑️ Removing stale order {order_id} (age: {age_sec:.0f}s)")
                        self.state_manager.remove_pending_order(order_id)
                    continue
                
                order_status = ''
                if isinstance(status, dict):
                    order_status = str(status.get('status', status.get('ordStatus', ''))).lower()
                
                if order_status in ('filled', 'closed', 'done', 'cancelled', 'canceled', 'expired'):
                    logger.info(f"   ✅ Order {order_id} on {exchange}: {order_status} — removing")
                    self.state_manager.remove_pending_order(order_id)
                elif order_status in ('new', 'open', 'partially_filled', 'active'):
                    # Cancel stale open orders to prevent unexpected fills
                    logger.warning(f"   🧹 Cancelling stale open order {order_id} on {exchange} ({symbol} {side})")
                    try:
                        await client.cancel_order(symbol, order_id)
                        logger.info(f"   ✅ Cancelled {order_id}")
                    except Exception as ce:
                        logger.warning(f"   ⚠️ Cancel failed: {ce}")
                    self.state_manager.remove_pending_order(order_id)
                else:
                    # Unknown status, remove if old
                    if age_sec > STALE_ORDER_TIMEOUT_SEC:
                        self.state_manager.remove_pending_order(order_id)
                    
            except Exception as e:
                logger.warning(f"   ⚠️ Error recovering order {order_id}: {e}")
                if age_sec > STALE_ORDER_TIMEOUT_SEC:
                    self.state_manager.remove_pending_order(order_id)
        
        remaining = len(self.state_manager.get_pending_orders())
        if remaining == 0:
            logger.info("🔄 RECOVERY: All pending orders processed ✅")
        else:
            logger.warning(f"🔄 RECOVERY: {remaining} orders still pending (will retry)")

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
            
            # Process orphaned pending orders from previous session
            await self._recover_pending_orders()
            
            # Risk Manager
            self.risk_manager = get_risk_manager()
            # Restore daily stats from state
            if self.state_manager.state.get("daily_pnl"):
                self.risk_manager.daily_pnl = self.state_manager.state["daily_pnl"]
            if self.state_manager.state.get("consecutive_losses"):
                self.risk_manager.consecutive_losses = self.state_manager.state["consecutive_losses"]
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
            
            # Engine 2.0: Capital Manager — adaptive modes by equity level
            initial_equity = settings.VIRTUAL_CAPITAL_PER_EXCHANGE * settings.NUM_EXCHANGES
            if not settings.DRY_RUN and self.balance_manager:
                try:
                    total = sum(
                        self.balance_manager.get_balance(ex, "USDT")
                        for ex in self.balance_manager.balances
                    )
                    if total > 0:
                        initial_equity = total
                except Exception:
                    pass
            self.capital_manager = CapitalManager(initial_equity=initial_equity)
            logger.info(f"✅ Capital Manager initialized: {self.capital_manager.get_summary()}")
            
            # Semi-HFT Engine
            self.semi_hft_engine = SemiHFTEngine()
            # Configure from settings
            if hasattr(settings, 'SEMI_HFT_MAX_RTT_MS'):
                self.semi_hft_engine.MAX_RTT_MS = settings.SEMI_HFT_MAX_RTT_MS
            if hasattr(settings, 'SEMI_HFT_LATENCY_KILL_MS'):
                self.semi_hft_engine.LATENCY_SPIKE_MS = settings.SEMI_HFT_LATENCY_KILL_MS
            if hasattr(settings, 'SEMI_HFT_SLIPPAGE_KILL_PCT'):
                self.semi_hft_engine.SLIPPAGE_SPIKE_PCT = settings.SEMI_HFT_SLIPPAGE_KILL_PCT
            if hasattr(settings, 'SEMI_HFT_MIN_FILL_RATE_PCT'):
                self.semi_hft_engine.MIN_FILL_RATE_PCT = settings.SEMI_HFT_MIN_FILL_RATE_PCT
            if hasattr(settings, 'SEMI_HFT_MIN_FILL_PROB'):
                self.semi_hft_engine.MAKER_MIN_FILL_PROBABILITY = settings.SEMI_HFT_MIN_FILL_PROB
            logger.info(f"✅ Semi-HFT Engine initialized: {self.semi_hft_engine.get_summary()}")
            
            # Wire semi_hft_engine into signal_allocator for top-exchange filtering
            self.signal_allocator.semi_hft_engine = self.semi_hft_engine
            
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
            
            # Analytics modules (optional — require numpy)
            self.trade_journal = TradeJournal() if TradeJournal else None
            self.performance_tracker = PerformanceTracker() if PerformanceTracker else None
            self.profit_attribution = ProfitAttributionAnalyzer() if ProfitAttributionAnalyzer else None
            self.risk_analytics = RiskAnalytics() if RiskAnalytics else None
            self.backtest_engine = BacktestEngine(initial_capital=10000) if BacktestEngine else None
            self.market_intelligence = MarketIntelligence() if MarketIntelligence else None
            self.realtime_analytics = RealtimeAnalytics() if RealtimeAnalytics else None
            self.correlation_analyzer = CorrelationAnalyzer() if CorrelationAnalyzer else None
            self.custom_dashboard = CustomDashboard() if CustomDashboard else None
            _analytics_count = sum(1 for x in [self.trade_journal, self.performance_tracker,
                self.profit_attribution, self.risk_analytics, self.backtest_engine,
                self.market_intelligence, self.realtime_analytics, self.correlation_analyzer,
                self.custom_dashboard] if x is not None)
            logger.info(f"{'✅' if _analytics_count == 9 else '⚠️'} Analytics: {_analytics_count}/9 initialized")
            
            # Professional Features (optional — require numpy)
            logger.info("\n🛡️  Initializing Professional Risk Features...")
            self.flash_crash_protector = FlashCrashProtector() if FlashCrashProtector else None
            self.wash_trading_filter = WashTradingFilter() if WashTradingFilter else None
            self.orderbook_imbalance_detector = OrderBookImbalanceDetector() if OrderBookImbalanceDetector else None
            _risk_count = sum(1 for x in [self.flash_crash_protector, self.wash_trading_filter,
                self.orderbook_imbalance_detector] if x is not None)
            logger.info(f"{'✅' if _risk_count == 3 else '⚠️'} Risk Features: {_risk_count}/3 initialized")
            
            # ML Modules (optional — require numpy/pandas)
            logger.info("\n🧠 Initializing ML Modules...")
            self.market_regime_detector = MarketRegimeDetector() if MarketRegimeDetector else None
            self.ml_spread_predictor = MLSpreadPredictor() if MLSpreadPredictor else None
            self.fee_optimizer = FeeOptimizer() if FeeOptimizer else None
            self.auto_parameter_optimizer = AutoParameterOptimizer() if AutoParameterOptimizer else None
            self.volatility_forecaster = VolatilityForecaster() if VolatilityForecaster else None
            self.nn_predictor = NeuralNetworkPredictor() if NeuralNetworkPredictor else None
            self.rl_agent = ReinforcementLearningAgent() if ReinforcementLearningAgent else None
            self.slippage_predictor = SlippagePredictor() if SlippagePredictor else None
            self.auto_parameter_tuner = AutoParameterTuner() if AutoParameterTuner else None
            self.pattern_recognition = PatternRecognition() if PatternRecognition else None
            self.market_adaptive_strategy = MarketAdaptiveStrategy() if MarketAdaptiveStrategy else None
            self.ml_model_trainer = MLModelTrainer() if MLModelTrainer else None
            _ml_count = sum(1 for x in [self.market_regime_detector, self.ml_spread_predictor,
                self.fee_optimizer, self.auto_parameter_optimizer, self.volatility_forecaster,
                self.nn_predictor, self.rl_agent, self.slippage_predictor, self.auto_parameter_tuner,
                self.pattern_recognition, self.market_adaptive_strategy, self.ml_model_trainer] if x is not None)
            logger.info(f"{'✅' if _ml_count == 12 else '⚠️'} ML Modules: {_ml_count}/12 initialized")
            
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
            
            # Phase 5: Professional Execution Modules (optional — require numpy)
            logger.info("\n🎯 Initializing Professional Execution Modules...")
            self.twap_engine = TWAPEngine() if TWAPEngine else None
            self.vwap_engine = VWAPEngine() if VWAPEngine else None
            self.iceberg_detector = IcebergOrderDetector() if IcebergOrderDetector else None
            self.order_flow_tracker = OrderFlowTracker() if OrderFlowTracker else None
            _exec_count = sum(1 for x in [self.twap_engine, self.vwap_engine,
                self.iceberg_detector, self.order_flow_tracker] if x is not None)
            logger.info(f"{'✅' if _exec_count == 4 else '⚠️'} Execution Modules: {_exec_count}/4 initialized")
            
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
                balance_manager=self.balance_manager,
                capital_manager=self.capital_manager,
                state_manager=self.state_manager,
                semi_hft_engine=self.semi_hft_engine,
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
                state_manager=self.state_manager,
                capital_manager=self.capital_manager,
                semi_hft_engine=self.semi_hft_engine,
            )
            # Provide REST clients for JIT inventory acquisition in live mode
            self.engine._rest_clients = self.rest_clients
            
            # §4 Event-driven: Wire PriceStore → Engine symbol update notifications
            if settings.EVENT_DRIVEN_SCAN:
                self.store.set_on_update(self.engine.mark_symbol_updated)
                logger.info("⚡ Event-driven scanning enabled (trigger on price change)")
            
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
            
            # Periodic latency re-ping task (updates exchange latency every 60s)
            if hasattr(self, 'semi_hft_engine') and self.semi_hft_engine and self.rest_clients:
                latency_task = asyncio.create_task(self._latency_ping_loop())
                self.tasks.append(latency_task)
                logger.info("✅ Periodic latency ping task started (every 60s)")
            
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
        """Static in-place dashboard — clears screen and redraws every cycle."""
        interval = settings.MONITOR_INTERVAL_SEC
        cycle = 0

        try:
            while True:
                await asyncio.sleep(interval)
                cycle += 1

                # ── Gather ALL data first ────────────────────────────
                snap = self.store.snapshot() if self.store else {}
                total_connections = sum(len(exmap) for exmap in snap.values()) if snap else 0
                active_symbols = len(snap) if snap else 0

                exchanges_with_data = set()
                for exmap in snap.values():
                    exchanges_with_data.update(exmap.keys())

                executor = getattr(self.engine, 'executor', None) if self.engine else None
                exec_stats = executor.get_statistics() if executor else {}
                total_trades = exec_stats.get('total_orders', 0)
                total_profit = exec_stats.get('total_profit', 0.0)
                avg_roi = exec_stats.get('average_roi', 0.0)

                disp_stats = {}
                if self.strategy_dispatcher:
                    disp_stats = self.strategy_dispatcher.strategy_stats

                # Capital & balance
                total_bal = 0.0
                if self.balance_manager:
                    total_bal = self.balance_manager.get_total_balance_usdt(
                        self.engine.store if self.engine else None)
                    if self.capital_manager:
                        self.capital_manager.update_equity(total_bal)
                        if self.engine and hasattr(self.engine, 'best_spread_pct'):
                            vol_pct = max(self.engine.best_spread_pct * 0.1, 0.001)
                            self.capital_manager.update_volatility(vol_pct)

                # Risk
                daily_pnl = self.risk_manager.daily_pnl if self.risk_manager else 0.0

                # Engine spread analytics
                best_spread = getattr(self.engine, '_best_spread_pct', 0) if self.engine else 0
                best_info = getattr(self.engine, '_best_spread_info', '') if self.engine else ''
                best_fees = getattr(self.engine, '_best_spread_fees_pct', 0) if self.engine else 0
                near_misses = getattr(self.engine, '_near_miss_count', 0) if self.engine else 0
                total_analyzed = getattr(self.engine, '_total_pairs_analyzed', 0) if self.engine else 0
                # Best NET spread = closest to profitability (shows MEXC-pairs advantage)
                best_net = getattr(self.engine, '_best_net_spread_pct', -99) if self.engine else -99
                best_net_info = getattr(self.engine, '_best_net_spread_info', '') if self.engine else ''
                best_net_fees = getattr(self.engine, '_best_net_spread_fees_pct', 0) if self.engine else 0

                # Threshold — use best NET pair's fees (most relevant to profitability)
                th_pct = 0.0
                th_fees = best_net_fees if best_net_fees > 0 else best_fees
                if self.capital_manager and th_fees > 0:
                    th_pct = self.capital_manager.dynamic_threshold(th_fees)

                # Signal allocator
                sa = getattr(self, 'signal_allocator', None)
                sa_coin = getattr(sa, '_current_coin', None) if sa else None
                sa_setup = getattr(sa, '_initial_setup_done', False) if sa else False
                sa_signals_all = len(getattr(sa, '_signals', [])) if sa else 0
                # Count only CROSS_EXCHANGE + positive ROI (what actually triggers pre-fund)
                sa_arb_signals = 0
                sa_best_sym = ""
                sa_best_count = 0
                if sa and hasattr(sa, '_signals'):
                    _sym_counts = defaultdict(int)
                    for _sig in sa._signals:
                        if hasattr(sa, '_is_profitable_signal') and sa._is_profitable_signal(_sig):
                            _sym_counts[_sig.symbol] += 1
                    sa_arb_signals = sum(_sym_counts.values())
                    if _sym_counts:
                        sa_best_sym = max(_sym_counts, key=_sym_counts.get)
                        sa_best_count = _sym_counts[sa_best_sym]
                sa_urgent = getattr(sa, '_urgent_rebalance_needed', False) if sa else False
                sa_misses = getattr(sa, '_misses', []) if sa else []
                recent_misses = sum(1 for m in sa_misses
                                    if time.time() - m.get('timestamp', 0) < 60)

                # HFT latencies from semi_hft_engine
                hft = getattr(self, 'semi_hft_engine', None)
                hft_latencies = {}
                if hft:
                    for ex, s in getattr(hft, '_latency', {}).items():
                        hft_latencies[ex] = s.ema_ms

                # ── Build the dashboard lines ────────────────────────
                W = 74  # total width
                mode = "DRY RUN" if settings.DRY_RUN else "LIVE"
                mode_icon = "TEST" if settings.DRY_RUN else "REAL"
                lines = []
                L = lines.append  # shortcut

                # ═══════ HEADER ═══════
                L(f"{'=' * W}")
                L(f"  ARBITRAGE BOT [{mode_icon}]   Cycle #{cycle}   "
                  f"{active_symbols} symbols   {total_connections} WS feeds")
                L(f"{'=' * W}")

                # ─── EXCHANGES ───
                L(f"  EXCHANGES:")
                all_ex = ['Binance', 'MEXC', 'KuCoin', 'Bybit', 'HTX']
                for ex in all_ex:
                    fee_pct = EXCHANGE_PARAMS.get(ex, {}).get('taker', 0) * 100
                    maker_pct = EXCHANGE_PARAMS.get(ex, {}).get('maker', fee_pct / 100) * 100
                    connected = "OK" if ex in exchanges_with_data else "OFF"
                    lat = hft_latencies.get(ex, 0)
                    lat_str = f"{lat:.0f}ms" if lat > 0 else "---"
                    # Determine if exchange is disabled by kill-logic
                    cm = self.capital_manager
                    disabled = ""
                    if cm and hasattr(cm, 'is_exchange_enabled'):
                        if not cm.is_exchange_enabled(ex):
                            disabled = " [DISABLED]"
                    icon = "+" if connected == "OK" else "-"
                    L(f"    [{icon}] {ex:<10} fee:{maker_pct:g}%/{fee_pct:g}%  "
                      f"lat:{lat_str:<8} {disabled}")

                # ─── CAPITAL & PROFIT ───
                L(f"{'─' * W}")
                L(f"  CAPITAL: ${total_bal:.2f} USDT")
                lvl_name = self.capital_manager.level.name if self.capital_manager else "N/A"
                compound = self.capital_manager.compound_multiplier if self.capital_manager else 1.0
                exec_mode = "SMART (MEXC=maker 0%, others=simultaneous)" if settings.MAKER_FIRST_ENABLED else "SIMULTANEOUS"
                L(f"  Level: {lvl_name}  |  Compound: {compound:.2f}x  |  "
                  f"Daily PnL: ${daily_pnl:.4f}")
                L(f"  Exec: {exec_mode}")
                L(f"  Trades: {total_trades}  |  Profit: ${total_profit:.4f}  |  "
                  f"Avg ROI: {avg_roi:.3f}%")
                if total_profit > 0 and self.engine:
                    reserved = getattr(self.engine, '_reserved_profit', 0.0)
                    L(f"  Reserve: ${reserved:.4f} (30% locked)")

                # ─── ACTIVE COIN & HOLDINGS ───
                L(f"{'─' * W}")
                if sa_coin and sa_setup:
                    base = sa_coin.split('-')[0] if '-' in sa_coin else sa_coin
                    L(f"  COIN: {sa_coin}")
                    if self.balance_manager:
                        parts = []
                        for ex in all_ex:
                            amt = self.balance_manager.get_balance(ex, base)
                            usdt = self.balance_manager.get_balance(ex, 'USDT')
                            if amt > 0 or usdt > 0:
                                parts.append(f"    {ex:<10} {base}:{amt:<10.4f} USDT:{usdt:.2f}")
                        for p in parts:
                            L(p)
                elif not sa_setup:
                    if sa_arb_signals > 0:
                        L(f"  COIN: collecting arb signals ({sa_best_count}/15 for {sa_best_sym})")
                        L(f"        {sa_arb_signals} arb / {sa_signals_all} total signals")
                    else:
                        L(f"  COIN: waiting for arb signals (0/15)")
                        L(f"        {sa_signals_all} total signals (none are cross-exchange arb)")
                else:
                    L(f"  COIN: none selected")

                # ─── SPREAD & THRESHOLD ANALYSIS ───
                L(f"{'─' * W}")
                if best_net > -99 and best_net_fees > 0:
                    # Show best NET spread (closest to profitability)
                    best_net_gross = best_net + best_net_fees  # recover gross
                    L(f"  BEST NET:     {best_net:+.4f}%  (spread {best_net_gross:.4f}% − fees {best_net_fees:.4f}%)  "
                      f"{best_net_info}")
                    L(f"  THRESHOLD:    {th_pct:.4f}%  (fees {th_fees:.4f}% + cushion)")
                    gap = th_pct - best_net_gross
                    if gap > 0:
                        L(f"  GAP:          {gap:.4f}%  (need {gap:.4f}% more spread to trade)")
                    else:
                        L(f"  >>> SPREAD ABOVE THRESHOLD — TRADES POSSIBLE!")
                elif best_spread > 0 and best_fees > 0:
                    pct_of_fees = best_spread / best_fees * 100
                    L(f"  BEST SPREAD:  {best_spread:.4f}%  ({pct_of_fees:.0f}% of fees)  "
                      f"{best_info}")
                    L(f"  THRESHOLD:    {th_pct:.4f}%")
                    gap = th_pct - best_spread
                    if gap > 0:
                        L(f"  GAP:          {gap:.4f}%  (need {gap:.4f}% more spread)")
                    else:
                        L(f"  >>> SPREAD ABOVE THRESHOLD — TRADES POSSIBLE!")
                else:
                    L(f"  SPREAD: no data yet")
                if total_analyzed > 0:
                    L(f"  Pairs scanned: {total_analyzed}  Near-misses: {near_misses}")

                # ─── WHAT IS THE BOT DOING? ───
                L(f"{'─' * W}")
                if sa_urgent:
                    L(f"  >> ACTION: BUYING COIN NOW (urgent rebalance)")
                elif not sa_setup and sa_arb_signals < 15:
                    if sa_arb_signals > 0:
                        L(f"  >> ACTION: Collecting arb signals ({sa_best_count}/15 for {sa_best_sym})")
                    else:
                        L(f"  >> ACTION: Waiting for cross-exchange arb signals (0/15)")
                elif recent_misses > 0:
                    L(f"  >> ACTION: {recent_misses} missed trades — waiting for rebalance")
                elif best_spread > 0 and th_pct > 0 and best_spread >= th_pct:
                    L(f"  >> ACTION: Executing arb trades!")
                else:
                    L(f"  >> ACTION: Scanning... best spread {best_spread:.3f}% < threshold {th_pct:.3f}%")

                # ─── STRATEGIES (only non-zero) ───
                active_strats = {k: v for k, v in disp_stats.items()
                                 if v.get('calls', 0) > 0 or v.get('trades', 0) > 0}
                if active_strats:
                    L(f"{'─' * W}")
                    L(f"  {'STRATEGY':<18} {'Scans':>7} {'Sigs':>6} {'Opps':>6} {'Trds':>6}")
                    for name, stats in active_strats.items():
                        L(f"  {name:<18} {stats.get('calls',0):>7} "
                          f"{stats.get('signals',0):>6} "
                          f"{stats.get('opportunities',0):>6} "
                          f"{stats.get('trades',0):>6}")

                # ─── HFT + ML (one line each) ───
                if hft:
                    vol_regime = getattr(hft, '_vol_regime', None)
                    vr = vol_regime.regime if vol_regime else "N/A"
                    L(f"{'─' * W}")
                    L(f"  HFT: VolRegime={vr}")

                # ML regime
                if self.market_regime_detector:
                    regimes = self.market_regime_detector.get_all_regimes()
                    if regimes:
                        from collections import Counter
                        rc = Counter(regimes.values())
                        top = rc.most_common(1)[0][0] if rc else 'N/A'
                        L(f"  ML:  Regime={top}")

                # ─── REJECTIONS (why trades don't happen) ───
                if self._rejection_total > 0:
                    L(f"{'─' * W}")
                    L(f"  REJECTIONS ({self._rejection_total} total):")
                    # Sort by count, show top 5
                    sorted_reasons = sorted(self._rejection_counts.items(),
                                            key=lambda x: x[1], reverse=True)
                    for reason, cnt in sorted_reasons[:5]:
                        bar_len = min(cnt * 30 // max(self._rejection_total, 1), 30)
                        bar = '#' * bar_len
                        L(f"    {reason:<30} {cnt:>6}  {bar}")

                # ─── RECENT ERRORS (from logging) ───
                recent_errors = _dashboard_error_handler.errors[-5:]
                if recent_errors:
                    L(f"{'─' * W}")
                    L(f"  ERRORS (last {len(recent_errors)}):")
                    for err in recent_errors:
                        # Truncate to fit width
                        err_short = err[:W - 6]
                        L(f"    {err_short}")

                # ═══════ FOOTER ═══════
                L(f"{'=' * W}")

                # ── Clear screen and print all at once ────────────────
                # Use ANSI escape: clear screen + move cursor to top
                output = ANSI_CLEAR_AND_HOME + '\n'.join(lines)
                sys.stdout.write(output + '\n')
                sys.stdout.flush()

                # Reset per-cycle engine metrics
                if self.engine:
                    self.engine._best_spread_pct = 0.0
                    self.engine._best_spread_info = ""
                    self.engine._best_spread_fees_pct = 0.0

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

    LATENCY_REPING_INTERVAL_SEC = 30  # Re-ping exchanges every 30 seconds (also re-syncs time)

    async def _latency_ping_loop(self):
        """Periodically re-ping ALL exchanges to update latency data.
        
        This allows excluded exchanges to recover if their latency improves.
        Without this, an exchange excluded at startup stays excluded FOREVER
        because no new latency measurements are ever recorded for it.
        """
        try:
            while True:
                await asyncio.sleep(self.LATENCY_REPING_INTERVAL_SEC)
                for name, client in self.rest_clients.items():
                    try:
                        t0 = time.time()
                        if hasattr(client, 'sync_server_time'):
                            await client.sync_server_time()
                        rtt_ms = (time.time() - t0) * 1000
                        if self.semi_hft_engine:
                            self.semi_hft_engine.record_latency(name, rtt_ms)
                        if self.engine:
                            self.engine.update_exchange_latency(name, rtt_ms)
                    except Exception as e:
                        logger.debug(f"Periodic ping failed for {name}: {e}")
        except asyncio.CancelledError:
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
                        and self.signal_allocator.has_sufficient_signals(15)
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
                        # Still searching for first coin — log per-symbol progress
                        from collections import defaultdict
                        symbol_counts = defaultdict(int)
                        for s in self.signal_allocator._signals:
                            if s.roi_pct > 0:
                                symbol_counts[s.symbol] += 1
                        if symbol_counts:
                            best_sym = max(symbol_counts, key=symbol_counts.get)
                            best_count = symbol_counts[best_sym]
                            logger.debug(
                                f"🔍 Searching for first coin... "
                                f"Best: {best_sym} with {best_count}/15 positive-ROI signals | "
                                f"Total symbols tracked: {len(symbol_counts)}"
                            )
                        else:
                            logger.debug("🔍 Searching for first coin... 0 positive-ROI signals so far")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Rebalance error: {e}")
                
                # Fast polling while searching, slow polling after first coin found
                interval = NORMAL_REBALANCE_INTERVAL if first_coin_found else INITIAL_POLL_INTERVAL
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            return
    
    async def _triangular_scan_loop(self):
        """Background task for triangular arbitrage scanning.
        
        Top arb bot pattern: execute BEST opportunity only (not all),
        to avoid depleting USDT balance across multiple simultaneous trades.
        """
        try:
            await asyncio.sleep(5)  # Wait for price data
            while True:
                try:
                    opps = self.triangular_engine.scan_opportunities()
                    if opps:
                        # Sort by profit descending — execute BEST one only
                        # (like top bots: don't spray orders, pick highest-EV trade)
                        opps.sort(key=lambda o: o['profit_pct'], reverse=True)
                        best = opps[0]
                        logger.debug(
                            f"🔺 TRI: {len(opps)} opps found, best: {best['route']} "
                            f"on {best['exchange']} profit={best['profit_pct']:.3f}%"
                        )
                        if self.executor:
                            result = await self.triangular_engine.execute_opportunity(best)
                            if result.get('status') == 'success':
                                logger.info(
                                    f"🔺 TRI EXECUTED: {best['route']} on {best['exchange']} "
                                    f"profit={best['profit_pct']:.3f}%"
                                )
                        if self.strategy_dispatcher:
                            self.strategy_dispatcher.strategy_stats['TRIANGULAR']['opportunities'] += len(opps)
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
                        logger.debug(f"🎯 Strategies found {len(executable)} executable opportunities (of {len(all_opps)} signals)")
                        trade_executed_this_cycle = False
                        for opp in executable:
                            # LIMIT: one trade per cycle to avoid balance race conditions
                            if trade_executed_this_cycle:
                                break
                            
                            trade_info = self._build_trade_from_signal(opp)
                            if trade_info:
                                # FILTER: Only trade the pre-funded coin
                                if (hasattr(self, 'signal_allocator') and self.signal_allocator
                                        and self.signal_allocator.get_current_coin()
                                        and trade_info['symbol'] != self.signal_allocator.get_current_coin()):
                                    continue
                                
                                # GATE: Skip if coins not yet positioned
                                if (hasattr(self, 'signal_allocator') and self.signal_allocator
                                        and not self.signal_allocator.is_ready_to_trade()):
                                    continue
                                
                                # Engine 2.0: Kill-logic checks (same as main engine)
                                if self.capital_manager:
                                    if not self.capital_manager.is_coin_enabled(trade_info['symbol']):
                                        logger.debug(f"CapitalManager: coin {trade_info['symbol']} disabled (kill-logic)")
                                        continue
                                    _buy_ex = trade_info.get('buy_ex', '')
                                    _sell_ex = trade_info.get('sell_ex', '')
                                    if _buy_ex and not self.capital_manager.is_exchange_enabled(_buy_ex):
                                        logger.debug(f"CapitalManager: exchange {_buy_ex} disabled (kill-logic)")
                                        continue
                                    if _sell_ex and not self.capital_manager.is_exchange_enabled(_sell_ex):
                                        logger.debug(f"CapitalManager: exchange {_sell_ex} disabled (kill-logic)")
                                        continue
                                
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
                                    trade_executed_this_cycle = True
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
                                    # Engine 2.0: Report to CapitalManager (kill-logic + quality ranking)
                                    if self.capital_manager:
                                        trade_result = result.get('trade_info', trade_info)
                                        roi_pct = trade_result.get('roi_pct', trade_info.get('roi_pct', 0))
                                        total_slippage = trade_result.get('buy_slippage_pct', 0) + trade_result.get('sell_slippage_pct', 0)
                                        self.capital_manager.record_trade_result(
                                            symbol=trade_info['symbol'],
                                            buy_exchange=trade_info.get('buy_ex', ''),
                                            sell_exchange=trade_info.get('sell_ex', ''),
                                            net_profit_pct=float(roi_pct),
                                            slippage_pct=float(total_slippage),
                                        )
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
                                    # Normalize symbol format: BTC/USDT → BTC-USDT (not just BTC)
                                    if '/' in sym:
                                        sym = sym.replace('/', '-')
                                    if sym:
                                        # Try multiple paths for roi_pct (use None checks, not falsy)
                                        data = opp.get('data', {})
                                        roi = opp.get('roi_pct')
                                        if roi is None:
                                            roi = data.get('roi_pct')
                                        if roi is None:
                                            roi = data.get('expected_profit')
                                        if roi is None:
                                            roi = data.get('spread_pct', 0)
                                        exch = data.get('exchange') or opp.get('exchange', '')
                                        self.signal_allocator.record_signal(
                                            symbol=sym,
                                            strategy=opp['strategy'],
                                            exchange=exch,
                                            roi_pct=float(roi) if roi else 0.0
                                        )
                
                await asyncio.sleep(settings.SCAN_INTERVAL_SEC)
                
        except asyncio.CancelledError:
            return
    
    def _is_executable(self, opp: dict) -> bool:
        """Check if a strategy signal has enough data to execute a trade.
        
        CRITICAL: Only strategies that identify cross-exchange price discrepancies
        are executable. Market observations (volatility, momentum, etc.) are 
        NOT executable on their own — they need a spread to profit from.
        """
        strategy = opp.get('strategy', '')
        data = opp.get('data', {})
        
        # Strategies that directly produce cross-exchange trade signals
        if strategy == 'TRIANGULAR':
            return True  # Has complete route and profit calculation
        if strategy == 'FUNDING_RATE' and data.get('deviation_pct', 0) > 0.1:
            return True  # Premium/discount detected between exchanges
        if strategy == 'INDEX_ARB' and abs(data.get('deviation_pct', 0)) > 0.1:
            return True  # Index vs component price difference
        
        # SMART_ORDER: only if spread is wide enough to potentially cover fees
        if strategy == 'SMART_ORDER':
            spread = data.get('spread_pct', 0)
            if spread > 0.10:  # Only if spread > 0.10% (close to fee coverage)
                return True
        
        # VOLATILITY_ARB: spread width difference between exchanges
        if strategy == 'VOLATILITY_ARB':
            spread_diff = data.get('spread_diff_pct', data.get('spread_pct', 0))
            if spread_diff > 0.10:
                return True
        
        # PAIRS_TRADING/SPREAD_BETTING: only extreme z-scores (statistical edge)
        if strategy in ('PAIRS_TRADING', 'SPREAD_BETTING'):
            z = abs(data.get('z_score', 0))
            if z > 2.0:  # Only execute on strong statistical signals
                return True
        
        # These are MARKET OBSERVATIONS, not executable trades:
        # VOLATILITY — just says coin is volatile, no trade direction
        # MOMENTUM — trend signal, not cross-exchange arb
        # BREAKOUT — price breakout, no exchange-pair trade
        # DCA — buy-the-dip signal, not cross-exchange
        # GRID_TRADING — grid position signal, not cross-exchange
        # MARKET_MAKING — spread observation, not a cross-exchange trade
        return False
    
    def _build_trade_from_signal(self, opp: dict) -> dict:
        """Convert a strategy signal into an executable trade dict.
        
        Uses PriceStore real-time data to find the best buy/sell exchange
        pair that aligns with the strategy signal.
        
        When a strategy produces a HIGH-CONFIDENCE signal (z-score > 2.0,
        RSI extreme, etc.), the required ROI threshold is reduced by up to
        50% because the statistical edge combines with the spread opportunity.
        """
        # STRATEGY SEPARATION: Directional strategies only generate signals, never trades
        strategy_name = opp.get('strategy', opp.get('data', {}).get('strategy', ''))
        if strategy_name in settings.DIRECTIONAL_STRATEGIES:
            return None  # Signal-only strategy, no trade execution

        # SLIPPAGE BUFFER: Reduce expected profit by estimated market impact
        # This accounts for the gap between simulation and actual execution
        SLIPPAGE_PER_LEG_PCT = 0.05  # 0.05% slippage per leg, applied to both legs
        roi_pct = opp.get('roi_pct', opp.get('data', {}).get('roi_pct', 0)) or 0
        if roi_pct > 0:
            adjusted_roi = roi_pct - SLIPPAGE_PER_LEG_PCT * 2  # Both legs
            if adjusted_roi <= 0:
                return None  # Not profitable after slippage estimate
            # Adjust net profit proportionally in the opportunity data
            net = opp.get('net', opp.get('data', {}).get('net', 0)) or 0
            if net > 0:
                opp_data = opp.get('data', opp)
                opp_data['net'] = net * (adjusted_roi / roi_pct)
                opp_data['roi_pct'] = adjusted_roi

        strategy = opp.get('strategy', '')
        symbol = opp.get('symbol', 'BTC-USDT')
        data = opp.get('data', {})
        
        # Normalize symbol to SYMBOL-USDT format
        if '/' in symbol:
            parts = symbol.split('/')
            symbol = f"{parts[0]}-{parts[1]}" if len(parts) == 2 else f"{parts[0]}-USDT"
        # If just a base currency like "BTC", add "-USDT"
        if '-' not in symbol and 'USDT' not in symbol:
            symbol = f"{symbol}-USDT"
        
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
        # §4 MAKER-FIRST: Buy side uses maker fee (limit order), sell side uses taker fee
        # MEXC maker=0% → buying on MEXC with limit order is FREE
        from core.exchange_config import EXCHANGE_PARAMS
        if settings.MAKER_FIRST_ENABLED:
            buy_fee = EXCHANGE_PARAMS.get(best_buy_ex, {}).get('maker', 0.001)
        else:
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
        # High-confidence signals add statistical edge, so we lower the bar
        # by up to 50% (NEVER more — must always cover fees).
        confidence = self._signal_confidence(strategy, data)
        min_roi = settings.MIN_NET_ROI_PCT * (1.0 - 0.5 * confidence)
        
        # HARD FLOOR: spread MUST exceed total fees — no exceptions.
        # Without this, "confidence" could push min_roi below 0 → guaranteed loss.
        total_fee_pct = (buy_fee + sell_fee) * 100
        spread_pct_raw = ((best_sell_price - best_buy_price) / best_buy_price) * 100 if best_buy_price > 0 else 0
        if spread_pct_raw <= total_fee_pct:
            # Spread doesn't cover fees — trade will LOSE money regardless of confidence
            gap = total_fee_pct - spread_pct_raw
            reason = f"spread<fees ({spread_pct_raw:.3f}%<{total_fee_pct:.3f}%, gap={gap:.3f}%)"
            self._track_rejection(reason, strategy, symbol, best_buy_ex, best_sell_ex, spread_pct_raw, total_fee_pct)
            return None
        
        # Only return if net profit is positive with sufficient margin
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
        
        IMPORTANT: Max confidence discount is 50% (see _build_trade_from_signal).
        This means even with confidence=1.0, min_roi is still ≥ 50% of MIN_NET_ROI_PCT.
        The trade MUST ALWAYS have spread > total fees regardless of confidence.
        """
        if strategy in ('PAIRS_TRADING', 'SPREAD_BETTING'):
            z = abs(data.get('z_score', 0))
            return min(z / 4.0, 1.0) if z > 2.0 else 0.0
        elif strategy == 'FUNDING_RATE':
            premium = abs(data.get('deviation_pct', data.get('premium_pct', 0)))
            return min(premium / 1.0, 1.0) if premium > 0.2 else 0.0
        elif strategy == 'INDEX_ARB':
            deviation = abs(data.get('deviation_pct', 0))
            return min(deviation / 0.5, 1.0) if deviation > 0.1 else 0.0
        elif strategy == 'VOLATILITY_ARB':
            return 0.2  # Small confidence bonus
        # All other strategies: NO confidence bonus
        # They don't provide statistical edge that justifies reduced ROI threshold
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
        
        # Log every 200th rejection at INFO so user sees trends without spam
        if self._rejection_total % 200 == 1:
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
        """Graceful shutdown — sell coins FIRST, then cancel tasks, save state."""
        # Prevent double-shutdown
        if getattr(self, '_shutdown_complete', False):
            return
        self._shutdown_complete = True
        
        logger.info("\n🛑 Shutting down gracefully...")
        
        # ========== §9.1 CANCEL ALL OPEN LIMIT ORDERS ==========
        # Do this FIRST — prevent stale limit orders from filling
        if hasattr(self, 'engine') and self.engine and self.engine.executor:
            try:
                await self.engine.executor.cancel_all_open_orders()
            except Exception as e:
                logger.error(f"⚠️ Error cancelling open orders: {e}")
        
        # ========== §9.2 SELL ALL COINS BACK TO USDT ==========
        # Do this BEFORE cancelling background tasks — WS feeds still alive for prices!
        # Shield from CancelledError: a second Ctrl+C must NOT abort the sell operation.
        SELL_TIMEOUT_SEC = 60  # Max 60 seconds for sell operation
        if hasattr(self, 'signal_allocator') and self.signal_allocator:
            try:
                price_store = getattr(self.engine, 'store', None) if hasattr(self, 'engine') and self.engine else None
                # asyncio.shield prevents a second CancelledError from aborting the sell
                await asyncio.wait_for(
                    asyncio.shield(
                        self.signal_allocator.sell_all_to_usdt(
                            rest_clients=self.rest_clients,
                            price_store=price_store,
                        )
                    ),
                    timeout=SELL_TIMEOUT_SEC,
                )
            except asyncio.CancelledError:
                logger.warning("⚠️ Second Ctrl+C detected during sell — still trying to complete...")
                # Try one more time without shield (last resort)
                try:
                    price_store = getattr(self.engine, 'store', None) if hasattr(self, 'engine') and self.engine else None
                    await asyncio.wait_for(
                        self.signal_allocator.sell_all_to_usdt(
                            rest_clients=self.rest_clients,
                            price_store=price_store,
                        ),
                        timeout=15,
                    )
                except Exception:
                    logger.error("⚠️ CRITICAL: sell_all_to_usdt failed after second Ctrl+C — coins may remain on exchanges!")
            except asyncio.TimeoutError:
                logger.error(f"⚠️ CRITICAL: sell_all_to_usdt timed out after {SELL_TIMEOUT_SEC}s — some coins may remain on exchanges!")
            except Exception as e:
                logger.error(f"⚠️ Error selling coins during shutdown: {e}")
        
        # NOW cancel all background tasks (WS feeds, monitors, etc.)
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
            
        except (KeyboardInterrupt, asyncio.CancelledError):
            # Ctrl+C on Windows raises CancelledError (via asyncio.run),
            # on Unix raises KeyboardInterrupt. Catch BOTH to ensure shutdown.
            logger.info("\n⚠️  Shutdown signal received (Ctrl+C)")
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
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 Goodbye!")
        sys.exit(0)
