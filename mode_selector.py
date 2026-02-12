"""
Mode Selector - Менеджер режимов работы бота
Позволяет переключаться между standard, ultra, ml и full режимами
"""
import os
import json
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class BotMode(Enum):
    """Режимы работы бота"""
    STANDARD = "standard"  # Базовый режим
    ULTRA = "ultra"        # С ULTRA оптимизациями
    ML = "ml"              # С машинным обучением
    FULL = "full"          # Полный режим (все модули)


class ModeSelector:
    """Класс для управления режимами работы бота"""
    
    def __init__(self):
        self.current_mode: Optional[BotMode] = None
        self.mode_history = []
        self.config_file = '.bot_mode.json'
        self._load_saved_mode()
        
    def _load_saved_mode(self):
        """Загрузить сохранённый режим"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    mode_value = data.get('mode')
                    if mode_value:
                        self.current_mode = BotMode(mode_value)
                        print(f"✅ Загружен сохранённый режим: {mode_value.upper()}")
            except Exception as e:
                print(f"⚠️  Ошибка загрузки режима: {e}")
                
    def _save_mode(self):
        """Сохранить текущий режим"""
        if self.current_mode:
            try:
                data = {
                    'mode': self.current_mode.value,
                    'timestamp': datetime.now().isoformat(),
                    'history': self.mode_history[-10:]  # Последние 10
                }
                with open(self.config_file, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"⚠️  Ошибка сохранения режима: {e}")
                
    def set_mode(self, mode: BotMode) -> bool:
        """
        Установить режим работы
        
        Args:
            mode: Режим работы (BotMode enum)
            
        Returns:
            bool: True если режим установлен успешно
        """
        if not isinstance(mode, BotMode):
            print(f"❌ Неверный тип режима: {type(mode)}")
            return False
            
        # Сохраняем в историю
        if self.current_mode:
            self.mode_history.append({
                'from': self.current_mode.value,
                'to': mode.value,
                'timestamp': datetime.now().isoformat()
            })
            
        self.current_mode = mode
        self._save_mode()
        
        print(f"✅ Режим установлен: {mode.value.upper()}")
        return True
        
    def get_current_mode(self) -> Optional[BotMode]:
        """Получить текущий режим"""
        return self.current_mode
        
    def get_mode_name(self) -> str:
        """Получить название текущего режима"""
        if self.current_mode:
            return self.current_mode.value.upper()
        return "НЕ УСТАНОВЛЕН"
        
    def is_mode_active(self, mode: BotMode) -> bool:
        """Проверить активен ли режим"""
        return self.current_mode == mode
        
    def is_standard_mode(self) -> bool:
        """Проверить - стандартный режим?"""
        return self.current_mode == BotMode.STANDARD
        
    def is_ultra_mode(self) -> bool:
        """Проверить - ULTRA режим?"""
        return self.current_mode == BotMode.ULTRA
        
    def is_ml_mode(self) -> bool:
        """Проверить - ML режим?"""
        return self.current_mode == BotMode.ML
        
    def is_full_mode(self) -> bool:
        """Проверить - полный режим?"""
        return self.current_mode == BotMode.FULL
        
    def switch_mode(self, new_mode: BotMode) -> bool:
        """
        Переключить режим (с проверками)
        
        Args:
            new_mode: Новый режим
            
        Returns:
            bool: True если переключение успешно
        """
        if self.current_mode == new_mode:
            print(f"ℹ️  Уже работает в режиме {new_mode.value.upper()}")
            return True
            
        print(f"🔄 Переключение {self.get_mode_name()} → {new_mode.value.upper()}")
        return self.set_mode(new_mode)
        
    def get_mode_info(self) -> Dict[str, Any]:
        """Получить информацию о текущем режиме"""
        if not self.current_mode:
            return {
                'mode': None,
                'name': 'НЕ УСТАНОВЛЕН',
                'active': False
            }
            
        return {
            'mode': self.current_mode.value,
            'name': self.current_mode.value.upper(),
            'enum': self.current_mode,
            'active': True,
            'timestamp': datetime.now().isoformat()
        }
        
    def get_history(self) -> list:
        """Получить историю переключений режимов"""
        return self.mode_history.copy()
        
    def reset_mode(self):
        """Сбросить режим (вернуться к standard)"""
        self.set_mode(BotMode.STANDARD)
        print("🔄 Режим сброшен на STANDARD")


# Singleton instance
_mode_selector_instance: Optional[ModeSelector] = None


def get_mode_selector() -> ModeSelector:
    """
    Получить singleton instance ModeSelector
    
    Returns:
        ModeSelector: Глобальный экземпляр менеджера режимов
    """
    global _mode_selector_instance
    
    if _mode_selector_instance is None:
        _mode_selector_instance = ModeSelector()
        
    return _mode_selector_instance


def get_current_mode() -> Optional[BotMode]:
    """
    Быстрый доступ к текущему режиму
    
    Returns:
        Optional[BotMode]: Текущий режим или None
    """
    return get_mode_selector().get_current_mode()


def is_standard_mode() -> bool:
    """Проверка - работает ли бот в стандартном режиме"""
    return get_mode_selector().is_standard_mode()


def is_ultra_mode() -> bool:
    """Проверка - работает ли бот в ULTRA режиме"""
    return get_mode_selector().is_ultra_mode()


def is_ml_mode() -> bool:
    """Проверка - работает ли бот в ML режиме"""
    return get_mode_selector().is_ml_mode()


def is_full_mode() -> bool:
    """Проверка - работает ли бот в полном режиме"""
    return get_mode_selector().is_full_mode()


# Примеры использования в коде:
"""
# В любом модуле можно проверить режим:

from mode_selector import get_current_mode, is_ultra_mode, BotMode

# Получить текущий режим
mode = get_current_mode()
if mode == BotMode.ULTRA:
    # Использовать ULTRA оптимизации
    use_ultra_optimizations()
    
# Или просто:
if is_ultra_mode():
    use_ultra_optimizations()

# Переключить режим:
from mode_selector import get_mode_selector
selector = get_mode_selector()
selector.set_mode(BotMode.ML)
"""
