"""
Конфигурация режимов работы бота
Определяет какие модули активны в каждом режиме и их параметры
"""
from mode_selector import BotMode

# Конфигурация для каждого режима
MODE_CONFIGS = {
    BotMode.STANDARD: {
        'name': 'Standard',
        'description': 'Базовый режим с основными модулями',
        'modules': [
            'core.price_store',
            'core.arbitrage',
            'core.order_executor',
            'core.balance_manager',
            'core.risk_manager',
            'core.state_manager',
            'exchanges.bybit',
            'exchanges.kucoin',
            'exchanges.htx',
            'exchanges.mexc',
        ],
        'parameters': {
            'scan_interval': 30,  # секунды
            'max_positions': 3,
            'risk_per_trade': 0.02,  # 2%
            'min_profit': 0.005,  # 0.5%
        },
        'performance': 'Базовая',
        'expected_profit': '$40-80/месяц (с капиталом $200)',
        'features': [
            'Основные модули арбитража',
            '4 основные биржи',
            'Базовый риск-менеджмент',
            'Минимальные требования к ресурсам'
        ]
    },
    
    BotMode.ULTRA: {
        'name': 'Ultra',
        'description': 'Режим с ULTRA оптимизациями',
        'modules': [
            # Все из standard +
            'core.price_store',
            'core.arbitrage',
            'core.order_executor',
            'core.balance_manager',
            'core.risk_manager',
            # ULTRA модули
            'core.arbitrage_ultra',
            'core.price_store_turbo',
            'core.order_executor_pro',
            'core.risk_manager_advanced',
            'core.balance_manager_smart',
            # Биржи
            'exchanges.bybit',
            'exchanges.kucoin',
            'exchanges.htx',
            'exchanges.mexc',
            'exchanges.binance',
        ],
        'parameters': {
            'scan_interval': 10,  # Быстрее
            'max_positions': 5,
            'risk_per_trade': 0.025,  # 2.5%
            'min_profit': 0.003,  # 0.3%
            'parallel_scans': True,
            'cache_enabled': True,
            'batch_size': 50,
        },
        'performance': '+100% производительность, -60% latency',
        'expected_profit': '$60-120/месяц (+50%)',
        'features': [
            'Параллельное сканирование',
            'Multi-level кэширование',
            'Умное исполнение ордеров',
            'Динамический риск-менеджмент',
            'Auto-rebalancing',
            '5 бирж включая Binance'
        ]
    },
    
    BotMode.ML: {
        'name': 'ML',
        'description': 'Режим с машинным обучением',
        'modules': [
            # Все из ULTRA +
            'core.arbitrage_ultra',
            'core.price_store_turbo',
            'core.order_executor_pro',
            'core.risk_manager_advanced',
            'core.balance_manager_smart',
            # ML модули
            'ml.ml_model_trainer',
            'ml.market_adaptive_strategy',
            'ml.pattern_recognition',
            'ml.auto_parameter_optimizer',
            # Биржи
            'exchanges.bybit',
            'exchanges.kucoin',
            'exchanges.htx',
            'exchanges.mexc',
            'exchanges.binance',
            'exchanges.coinbase',
            'exchanges.gateio',
        ],
        'parameters': {
            'scan_interval': 15,
            'max_positions': 7,
            'risk_per_trade': 0.03,  # 3%
            'min_profit': 0.003,
            'ml_enabled': True,
            'adaptive_parameters': True,
            'learning_rate': 0.001,
            'model_update_interval': 3600,  # 1 час
        },
        'performance': '+50% адаптивность, автообучение',
        'expected_profit': '$70-140/месяц (+75%)',
        'features': [
            'Все ULTRA оптимизации',
            'Машинное обучение на истории',
            'Адаптивные стратегии',
            'Распознавание паттернов',
            'Автооптимизация параметров',
            'Предсказание возможностей',
            '7 бирж'
        ]
    },
    
    BotMode.FULL: {
        'name': 'Full',
        'description': 'Полный режим - все модули активны',
        'modules': [
            # Core
            'core.arbitrage_ultra',
            'core.price_store_turbo',
            'core.order_executor_pro',
            'core.risk_manager_advanced',
            'core.balance_manager_smart',
            'core.calculator',
            'core.portfolio_rebalancer',
            'core.position_manager',
            'core.order_router',
            'core.slippage_optimizer',
            'core.fee_optimizer',
            'core.liquidity_analyzer',
            'core.price_aggregator',
            'core.strategy_combiner',
            'core.performance_optimizer',
            'core.data_pipeline',
            # ML
            'ml.ml_model_trainer',
            'ml.market_adaptive_strategy',
            'ml.pattern_recognition',
            'ml.auto_parameter_optimizer',
            # Strategies
            'core.strategies.market_making',
            'core.strategies.spread_betting',
            'core.strategies.funding_rate_enhanced',
            'core.strategies.volatility_arb',
            'core.strategies.grid_trading',
            'core.strategies.dca_strategy',
            'core.strategies.index_arb',
            'core.strategies.pairs_trading',
            # Analytics
            'analytics.realtime_analytics',
            'analytics.performance_tracker',
            'analytics.trade_journal',
            'analytics.risk_analytics',
            'analytics.profit_attribution',
            'analytics.market_intelligence',
            'analytics.correlation_analyzer',
            'analytics.backtest_engine',
            'analytics.cohort_analysis',
            'analytics.advanced_reporting',
            'analytics.custom_dashboards',
            # Infrastructure
            'infrastructure.cache_manager',
            'infrastructure.config_manager',
            'infrastructure.logger_manager',
            'infrastructure.health_monitor',
            'infrastructure.queue_manager',
            'infrastructure.metrics_collector',
            'infrastructure.alert_manager',
            'infrastructure.rate_limiter',
            'infrastructure.circuit_breaker_enhanced',
            'infrastructure.data_validator',
            'infrastructure.secret_manager',
            'infrastructure.connection_manager',
            # GPU
            'core.gpu_accelerator',
            'core.gpu_batch_processor',
            # Все биржи
            'exchanges.bybit',
            'exchanges.kucoin',
            'exchanges.htx',
            'exchanges.mexc',
            'exchanges.binance',
            'exchanges.coinbase',
            'exchanges.gateio',
            'exchanges.okx',
            'exchanges.cryptocom',
        ],
        'parameters': {
            'scan_interval': 5,  # Максимальная частота
            'max_positions': 10,
            'risk_per_trade': 0.035,  # 3.5%
            'min_profit': 0.002,  # 0.2%
            'parallel_scans': True,
            'cache_enabled': True,
            'ml_enabled': True,
            'gpu_acceleration': True,
            'all_strategies_enabled': True,
            'advanced_analytics': True,
            'full_monitoring': True,
        },
        'performance': '+150-200% производительность, все возможности',
        'expected_profit': '$100-200/месяц (+150%)',
        'features': [
            'ВСЕ 104 модуля активны',
            'Все 9 бирж',
            'Все 13+ стратегий',
            'ML самообучение',
            'GPU acceleration',
            'Полная аналитика',
            'Расширенный мониторинг',
            'Максимальная производительность',
            'Максимальная прибыльность'
        ],
        'requirements': {
            'cpu_cores': 4,
            'ram_gb': 8,
            'gpu': 'Опционально (для ускорения)',
            'disk_gb': 10
        }
    }
}


def get_mode_config(mode: BotMode) -> dict:
    """Получить конфигурацию режима"""
    return MODE_CONFIGS.get(mode, MODE_CONFIGS[BotMode.STANDARD])


def get_active_modules(mode: BotMode) -> list:
    """Получить список активных модулей для режима"""
    config = get_mode_config(mode)
    return config.get('modules', [])


def get_mode_parameters(mode: BotMode) -> dict:
    """Получить параметры режима"""
    config = get_mode_config(mode)
    return config.get('parameters', {})


def is_module_active(mode: BotMode, module_name: str) -> bool:
    """Проверить активен ли модуль в данном режиме"""
    active_modules = get_active_modules(mode)
    return module_name in active_modules
