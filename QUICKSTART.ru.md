# Быстрый Старт - Арбитражный Бот

**Ветка**: `copilot/cleanup-stabilization-pass`  
**Репозиторий**: https://github.com/tsepper002/arbitrage-bot

Это руководство поможет вам установить и запустить арбитражного бота на вашем железе менее чем за 5 минут.

> **📖 Возникли проблемы?** См. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) для решения типичных проблем.

---

## 🚀 Установка и Запуск Одной Командой

### Windows (PowerShell)

```powershell
# Клонирование, установка зависимостей и запуск
git clone -b copilot/cleanup-stabilization-pass https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Linux / macOS

```bash
# Клонирование, установка зависимостей и запуск
git clone -b copilot/cleanup-stabilization-pass https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## 📋 Пошаговая Установка

### Требования

- **Python 3.9+** ([Скачать](https://www.python.org/downloads/))
- **Git** ([Скачать](https://git-scm.com/downloads))
- **Интернет-соединение** (для WebSocket подключений)

### 1. Клонирование Репозитория

```bash
git clone -b copilot/cleanup-stabilization-pass https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot
```

> **⚠️ Важно:** Убедитесь что клонируете ветку `copilot/cleanup-stabilization-pass`! Эта ветка включает все исправления для Windows и удалённые emoji символы.

### 2. Проверка Правильной Версии

Убедитесь что у вас правильная версия:

```bash
# Проверка ветки
git branch
# Должно показать: * copilot/cleanup-stabilization-pass

# Проверка размера main.py (должно быть ~136 строк, не 900+)
wc -l main.py
# Или на Windows: python -c "print(len(open('main.py').readlines()))"
```

Если видите проблемы или неправильную версию, см. [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### 3. Создание Виртуального Окружения (Рекомендуется)

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Установка Зависимостей

```bash
pip install -r requirements.txt
```

**Необходимые пакеты:**
- `aiohttp` - Асинхронный HTTP клиент
- `websockets` - WebSocket протокол
- `websocket-client` - Библиотека WebSocket клиента
- `requests` - HTTP библиотека

### 5. Проверка Установки

```bash
python test_core.py
```

Вы должны увидеть:
```
[OK] ALL TESTS PASSED
```

Если видите ошибки, проверьте [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### 6. Запуск Бота (Режим Сухого Запуска - Безопасно)

```bash
python main.py
```

Бот будет:
- ✅ Подключаться к биржам Bybit, KuCoin и HTX
- ✅ Мониторить книги заказов в реальном времени
- ✅ Обнаруживать арбитражные возможности
- ✅ Логировать потенциальные сделки (БЕЗ РЕАЛЬНЫХ ОРДЕРОВ)

---

## ⚙️ Быстрая Настройка

Просмотр текущих настроек:
```bash
python settings.py
```

### Изменение Торговых Пар

Отредактируйте `settings.py` или установите переменную окружения:

**Windows:**
```powershell
$env:ARB_SYMBOLS="BTC-USDT,ETH-USDT,SOL-USDT"
python main.py
```

**Linux/Mac:**
```bash
export ARB_SYMBOLS="BTC-USDT,ETH-USDT,SOL-USDT"
python main.py
```

### Настройка Под Ваше Железо

**Мощное Железо (По Умолчанию):**
```bash
# settings.py уже оптимизирован
python main.py
```

**Слабое/Ноутбук:**

Отредактируйте `settings.py`:
```python
SCAN_INTERVAL_SEC = 2.0          # Медленное сканирование (меньше CPU)
MONITOR_INTERVAL_SEC = 10.0       # Меньше логов
TRADING_SYMBOLS = ["BTC-USDT", "ETH-USDT"]  # Меньше пар
```

Или используйте переменные окружения:
```bash
export ARB_SCAN_INTERVAL_SEC=2.0
export ARB_MONITOR_INTERVAL_SEC=10.0
export ARB_SYMBOLS="BTC-USDT,ETH-USDT"
python main.py
```

---

## 🛠️ Решение Проблем

### Проблема: Ошибки "Module not found"

**Решение:** Убедитесь что виртуальное окружение активировано и зависимости установлены
```bash
# Активация venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\Activate.ps1  # Windows

# Переустановка зависимостей
pip install -r requirements.txt
```

### Проблема: Таймаут соединения или ошибки WebSocket

**Решение 1:** Проверьте интернет-соединение и настройки брандмауэра

**Решение 2:** Windows Firewall - Разрешите Python в брандмауэре
1. Безопасность Windows → Брандмауэр и защита сети
2. Разрешить приложение через брандмауэр
3. Найдите Python, включите Частные и Публичные сети

**Решение 3:** Попробуйте с меньшим количеством пар
```bash
export ARB_SYMBOLS="BTC-USDT"
python main.py
```

### Проблема: Высокая загрузка CPU

**Решение:** Уменьшите частоту сканирования и количество отслеживаемых пар
```bash
export ARB_SCAN_INTERVAL_SEC=3.0
export ARB_SYMBOLS="BTC-USDT,ETH-USDT"
python main.py
```

### Проблема: Ошибки Unicode/Emoji на Windows

**Решение:** Эта ветка включает исправления для проблем с Unicode на Windows. Если ошибки всё ещё появляются, убедитесь что используете Python 3.9+ из Microsoft Store или python.org.

### Проблема: "Арбитражные возможности не найдены"

**Это нормально!** Арбитражные возможности редки. Боту нужно работать непрерывно чтобы их поймать. В режиме сухого запуска может потребоваться от нескольких минут до часов чтобы обнаружить возможности в зависимости от рыночных условий.

---

## 📊 Понимание Вывода

### Статус Подключения
```
[OK] Bybit: Connected
[OK] KuCoin: Connected
[OK] HTX: Connected
```

### Обнаружена Арбитражная Возможность
```
[DRY RUN] ARBITRAGE OPPORTUNITY DETECTED
   Symbol: BTC-USDT
   Buy:  0.001000 @ $45000.50 on KuCoin (cost: $45.00)
   Sell: 0.001000 @ $45050.75 on Bybit (receive: $45.05)
   Net Profit: $0.0234 (0.052% ROI)
```

### Мониторинг Здоровья
```
[OK] Bybit Health: Connected=True, Uptime=120s, Messages=1547, Symbols=10
```

---

## 🔐 Функции Безопасности

✅ **Режим Сухого Запуска по Умолчанию** - Без реальных сделок пока не включено явно  
✅ **Ограничение Частоты** - Максимум 5 сделок в минуту  
✅ **Периоды Охлаждения** - 30с между сделками по одной паре  
✅ **Лимиты Экспозиции** - Максимум $200 на сделку  
✅ **Фактор Безопасности** - Использует только 50% доступной ликвидности  

---

## 📚 Следующие Шаги

1. **Прочитайте полный README.md** для подробных опций конфигурации
2. **Мониторьте бота** несколько часов чтобы понять его поведение
3. **Настройте параметры** под ваше железо и риск-профиль
4. **Изучите IMPLEMENTATION_SUMMARY.md** для технических деталей

---

## ⚠️ Важные Замечания

- **Режим Сухого Запуска по Умолчанию** - Бот НЕ будет размещать реальные ордера без конфигурации
- **Живая Торговля Требует Настройки** - API ключи бирж, аутентификация и тщательная конфигурация
- **Не Финансовый Совет** - Это образовательное ПО. Используйте на свой риск.
- **Тщательно Тестируйте** - Всегда запускайте в режиме сухого запуска на новом железе сначала

---

## 🐛 Получение Помощи

- **Проблемы**: https://github.com/tsepper002/arbitrage-bot/issues
- **Полная Документация**: См. README.md в этом репозитории
- **Тесты**: Запустите `python test_core.py` для проверки установки

---

**Готовы начать? Запустите:**
```bash
python main.py
```

**Успешной торговли! (безопасно в режиме сухого запуска)** 🚀
