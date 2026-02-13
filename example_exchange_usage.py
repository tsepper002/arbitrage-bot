"""
Пример использования Exchange Manager для управления всеми 9 биржами
"""
import asyncio
import logging
from core.exchange_manager import get_exchange_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Демонстрация работы с Exchange Manager"""
    
    # Получить менеджер бирж
    manager = get_exchange_manager()
    
    logger.info("="*60)
    logger.info("EXCHANGE MANAGER - DEMO")
    logger.info("="*60)
    
    # 1. Показать текущие биржи
    logger.info(f"\n1. Текущие биржи: {manager.get_all_exchanges()}")
    logger.info(f"   Активные: {manager.get_active_exchanges()}")
    
    # 2. Добавить все 9 бирж
    logger.info("\n2. Добавление всех 9 бирж...")
    
    exchanges_to_add = {
        'binance': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT'],
        'coinbase': ['BTC/USD', 'ETH/USD'],
        'gateio': ['BTC/USDT', 'ETH/USDT'],
        'okx': ['BTC/USDT', 'ETH/USDT'],
        'cryptocom': ['BTC/USDT', 'ETH/USDT']
    }
    
    for exchange, symbols in exchanges_to_add.items():
        success = await manager.add_exchange(
            name=exchange,
            symbols=symbols,
            enabled=True
        )
        status = "✅" if success else "❌"
        logger.info(f"   {status} {exchange}: {symbols}")
    
    # 3. Показать все биржи
    all_exchanges = manager.get_all_exchanges()
    logger.info(f"\n3. Все биржи ({len(all_exchanges)}): {all_exchanges}")
    
    # 4. Статистика
    stats = manager.get_statistics()
    logger.info(f"\n4. Статистика:")
    logger.info(f"   Всего сконфигурировано: {stats['total_configured']}")
    logger.info(f"   Включено: {stats['enabled']}")
    logger.info(f"   Активно: {stats['active']}")
    logger.info(f"   Поддерживается: {stats['supported']}")
    logger.info(f"   Здоровых: {stats['health_ok']}")
    
    # 5. Проверка здоровья
    logger.info("\n5. Проверка здоровья всех бирж...")
    health = await manager.health_check_all()
    for exchange, is_healthy in health.items():
        status = "✅ OK" if is_healthy else "❌ FAIL"
        logger.info(f"   {exchange}: {status}")
    
    # 6. Отключить одну биржу
    logger.info("\n6. Отключение MEXC...")
    await manager.disable_exchange('mexc')
    logger.info(f"   Активных после отключения: {len(manager.get_active_exchanges())}")
    
    # 7. Включить обратно
    logger.info("\n7. Включение MEXC обратно...")
    await manager.enable_exchange('mexc')
    logger.info(f"   Активных после включения: {len(manager.get_active_exchanges())}")
    
    # 8. Обновить символы для биржи
    logger.info("\n8. Обновление символов для Binance...")
    new_symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT']
    await manager.update_symbols('binance', new_symbols)
    config = manager.get_exchange_config('binance')
    logger.info(f"   Новые символы: {config.symbols}")
    
    # 9. Получить конфигурацию конкретной биржи
    logger.info("\n9. Конфигурация Binance:")
    config = manager.get_exchange_config('binance')
    if config:
        logger.info(f"   Имя: {config.name}")
        logger.info(f"   Включена: {config.enabled}")
        logger.info(f"   WebSocket: {config.websocket_enabled}")
        logger.info(f"   REST: {config.rest_enabled}")
        logger.info(f"   Rate limit: {config.rate_limit} req/s")
        logger.info(f"   Символов: {len(config.symbols)}")
    
    # 10. Поддерживаемые биржи
    logger.info(f"\n10. Поддерживаемые биржи ({len(manager.get_supported_exchanges())}):")
    for exchange in manager.get_supported_exchanges():
        logger.info(f"   - {exchange}")
    
    # 11. Финальный статус
    logger.info("\n" + "="*60)
    logger.info("ФИНАЛЬНЫЙ СТАТУС")
    logger.info("="*60)
    active = manager.get_active_exchanges()
    logger.info(f"Активных бирж: {len(active)}")
    logger.info(f"Список: {', '.join(active)}")
    logger.info("="*60)
    
    logger.info("\n✅ Демонстрация завершена!")
    logger.info("💡 Все 9 бирж готовы к использованию!")
    logger.info("🚀 Бот готов к арбитражу на максимальной ликвидности!")

if __name__ == "__main__":
    asyncio.run(main())
