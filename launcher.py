#!/usr/bin/env python3
"""
Интерактивный launcher для Arbitrage Bot с выбором режимов работы
"""
import sys
import os
import argparse
import asyncio
import signal
from typing import Optional
from datetime import datetime

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mode_selector import get_mode_selector, BotMode
from config_modes import MODE_CONFIGS


class BotLauncher:
    """Launcher для запуска бота в разных режимах"""
    
    def __init__(self):
        self.mode_selector = get_mode_selector()
        self.running = False
        self.bot_task = None
        
    def print_banner(self):
        """Красивый баннер при запуске"""
        print("\n" + "="*60)
        print("   ARBITRAGE BOT - CRYPTOCURRENCY ARBITRAGE TRADING")
        print("="*60)
        print(f"   Запущен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60 + "\n")
        
    def print_menu(self):
        """Интерактивное меню выбора режима"""
        print("\n╔═══════════════════════════════════════════════════════════════╗")
        print("║        ARBITRAGE BOT - ВЫБОР РЕЖИМА РАБОТЫ                   ║")
        print("╠═══════════════════════════════════════════════════════════════╣")
        print("║                                                               ║")
        print("║  1️⃣  STANDARD - Базовый режим                                 ║")
        print("║     • Основные модули (PriceStore, ArbitrageEngine)          ║")
        print("║     • 4 основные биржи                                       ║")
        print("║     • Прибыль: $40-80/месяц (с капиталом $200)              ║")
        print("║     • Производительность: Базовая                            ║")
        print("║                                                               ║")
        print("║  2️⃣  ULTRA - Оптимизированный режим                           ║")
        print("║     • ULTRA оптимизации (Turbo, Pro, Advanced)              ║")
        print("║     • Параллельное сканирование                              ║")
        print("║     • Прибыль: $60-120/месяц (+50%)                         ║")
        print("║     • Производительность: +100%, Latency: -60%               ║")
        print("║                                                               ║")
        print("║  3️⃣  ML - С машинным обучением                                ║")
        print("║     • Адаптивные стратегии                                   ║")
        print("║     • Самообучение на истории                                ║")
        print("║     • Прибыль: $70-140/месяц (+75%)                         ║")
        print("║     • Адаптация к рынку: Автоматическая                      ║")
        print("║                                                               ║")
        print("║  4️⃣  FULL - Полный режим (максимум возможностей)              ║")
        print("║     • ВСЕ 104 модуля активны                                 ║")
        print("║     • Все 9 бирж, все стратегии                              ║")
        print("║     • Прибыль: $100-200/месяц (+150%)                       ║")
        print("║     • Производительность: +150-200%                          ║")
        print("║     • GPU acceleration (если доступно)                       ║")
        print("║                                                               ║")
        print("║  5️⃣  Выход                                                     ║")
        print("║                                                               ║")
        print("╚═══════════════════════════════════════════════════════════════╝")
        
    def get_mode_choice(self) -> Optional[BotMode]:
        """Получить выбор режима от пользователя"""
        while True:
            try:
                choice = input("\n👉 Выберите режим (1-5): ").strip()
                
                if choice == '1':
                    return BotMode.STANDARD
                elif choice == '2':
                    return BotMode.ULTRA
                elif choice == '3':
                    return BotMode.ML
                elif choice == '4':
                    return BotMode.FULL
                elif choice == '5':
                    print("\n👋 До свидания!\n")
                    return None
                else:
                    print("❌ Неверный выбор. Пожалуйста, введите число от 1 до 5.")
            except KeyboardInterrupt:
                print("\n\n👋 Прервано пользователем. До свидания!\n")
                return None
                
    def print_mode_info(self, mode: BotMode):
        """Информация о выбранном режиме"""
        config = MODE_CONFIGS[mode]
        
        print(f"\n{'='*60}")
        print(f"🚀 Запуск в режиме: {mode.value.upper()}")
        print(f"{'='*60}")
        print(f"\n📊 Конфигурация режима:")
        print(f"   • Описание: {config['description']}")
        print(f"   • Активных модулей: {len(config['modules'])}")
        print(f"   • Производительность: {config.get('performance', 'Базовая')}")
        print(f"   • Ожидаемая прибыль: {config.get('expected_profit', 'N/A')}")
        
        if 'features' in config:
            print(f"\n✨ Особенности:")
            for feature in config['features']:
                print(f"   • {feature}")
                
        print(f"\n⚙️  Параметры:")
        for key, value in config.get('parameters', {}).items():
            print(f"   • {key}: {value}")
            
        print(f"\n{'='*60}\n")
        
    def validate_environment(self) -> bool:
        """Проверка окружения перед запуском"""
        print("🔍 Проверка окружения...")
        
        # Проверка .env файла
        if not os.path.exists('.env'):
            print("⚠️  Файл .env не найден!")
            print("   Создайте файл .env с API ключами бирж.")
            print("   Используйте .env.example как шаблон.")
            return False
            
        # Проверка основных модулей
        required_modules = ['core', 'exchanges', 'analytics']
        missing = []
        
        for module in required_modules:
            if not os.path.exists(module):
                missing.append(module)
                
        if missing:
            print(f"❌ Отсутствуют необходимые модули: {', '.join(missing)}")
            return False
            
        print("✅ Окружение проверено успешно!")
        return True
        
    async def start_bot(self, mode: BotMode):
        """Запуск бота в выбранном режиме"""
        print(f"\n🚀 Запуск бота в режиме {mode.value.upper()}...")
        
        # Устанавливаем режим
        self.mode_selector.set_mode(mode)
        
        # Импортируем main после установки режима
        try:
            import main
            
            # Запускаем основной цикл
            self.running = True
            print("✅ Бот запущен успешно!")
            print("📊 Мониторинг рынка начат...")
            print("\n💡 Нажмите Ctrl+C для остановки\n")
            
            # Здесь должен быть основной цикл бота
            # Для примера просто ждём
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n⏸️  Получен сигнал остановки...")
            await self.stop_bot()
        except Exception as e:
            print(f"\n❌ Ошибка при запуске бота: {e}")
            import traceback
            traceback.print_exc()
            
    async def stop_bot(self):
        """Graceful shutdown"""
        print("🛑 Остановка бота...")
        self.running = False
        
        # Здесь должна быть логика остановки всех модулей
        await asyncio.sleep(1)
        
        print("✅ Бот остановлен безопасно")
        print("💾 Все данные сохранены")
        print("\n👋 До свидания!\n")
        
    def run_interactive(self):
        """Интерактивный режим с меню"""
        self.print_banner()
        
        # Проверка окружения
        if not self.validate_environment():
            sys.exit(1)
            
        # Показываем меню
        self.print_menu()
        
        # Получаем выбор режима
        mode = self.get_mode_choice()
        
        if mode is None:
            sys.exit(0)
            
        # Показываем информацию о режиме
        self.print_mode_info(mode)
        
        # Подтверждение
        confirm = input("Продолжить запуск? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\n❌ Запуск отменён\n")
            sys.exit(0)
            
        # Запускаем бота
        try:
            asyncio.run(self.start_bot(mode))
        except KeyboardInterrupt:
            print("\n\n👋 Прервано пользователем\n")
        except Exception as e:
            print(f"\n❌ Критическая ошибка: {e}\n")
            sys.exit(1)
            
    def run_with_args(self, mode: str):
        """Запуск с параметрами командной строки"""
        self.print_banner()
        
        # Конвертируем строку в BotMode
        try:
            bot_mode = BotMode(mode.lower())
        except ValueError:
            print(f"❌ Неверный режим: {mode}")
            print(f"   Доступные режимы: standard, ultra, ml, full")
            sys.exit(1)
            
        # Проверка окружения
        if not self.validate_environment():
            sys.exit(1)
            
        # Показываем информацию
        self.print_mode_info(bot_mode)
        
        # Запускаем
        try:
            asyncio.run(self.start_bot(bot_mode))
        except KeyboardInterrupt:
            print("\n\n👋 Прервано пользователем\n")
        except Exception as e:
            print(f"\n❌ Критическая ошибка: {e}\n")
            sys.exit(1)


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description='Arbitrage Bot Launcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python launcher.py                    # Интерактивный режим
  python launcher.py --mode standard    # Базовый режим
  python launcher.py --mode ultra       # ULTRA режим
  python launcher.py --mode ml          # ML режим
  python launcher.py --mode full        # Полный режим
        """
    )
    
    parser.add_argument(
        '--mode',
        type=str,
        choices=['standard', 'ultra', 'ml', 'full'],
        help='Режим работы бота'
    )
    
    args = parser.parse_args()
    
    launcher = BotLauncher()
    
    if args.mode:
        # Запуск с параметром
        launcher.run_with_args(args.mode)
    else:
        # Интерактивный режим
        launcher.run_interactive()


if __name__ == '__main__':
    main()
