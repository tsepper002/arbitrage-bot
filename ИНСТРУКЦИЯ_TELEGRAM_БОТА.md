# 🤖 ИНСТРУКЦИЯ: Настройка Telegram Бота

**Проблема:** "Telegram бот только пишет что бот запустился"

**Решение:** Полная инструкция по созданию и настройке Telegram бота!

---

## 📋 СОДЕРЖАНИЕ

1. [Создание бота через BotFather](#1-создание-бота)
2. [Получение токена](#2-получение-токена)
3. [Настройка settings.py](#3-настройка-settingspy)
4. [Как найти Chat ID](#4-как-найти-chat-id)
5. [Запуск и тестирование](#5-запуск-и-тестирование)
6. [Использование команд](#6-использование-команд)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Создание Бота

### Шаг 1.1: Открыть Telegram

Откройте Telegram на телефоне или компьютере

### Шаг 1.2: Найти BotFather

1. В поиске введите: `@BotFather`
2. Это официальный бот для создания ботов (синяя галочка)
3. Нажмите "START" или отправьте `/start`

### Шаг 1.3: Создать нового бота

Отправьте команду:
```
/newbot
```

BotFather спросит:
```
Alright, a new bot. How are we going to call it? 
Please choose a name for your bot.
```

### Шаг 1.4: Придумать имя

Введите имя бота, например:
```
My Arbitrage Bot
```

### Шаг 1.5: Придумать username

BotFather попросит username (должен заканчиваться на "bot"):
```
Good. Now let's choose a username for your bot. 
It must end in `bot`. Like this, for example: TetrisBot or tetris_bot.
```

Введите, например:
```
my_arbitrage_trading_bot
```

**Важно:** Username должен быть уникальным и заканчиваться на `bot`

---

## 2. Получение Токена

### После создания бота

BotFather отправит сообщение:
```
Done! Congratulations on your new bot. You will find it at 
t.me/my_arbitrage_trading_bot. You can now add a description...

Use this token to access the HTTP API:
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890

For a description of the Bot API, see this page: 
https://core.telegram.org/bots/api
```

### Скопировать токен

**Токен выглядит так:**
```
1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890
```

**⚠️ ВАЖНО:** 
- Никому не показывайте токен!
- С токеном кто угодно может управлять вашим ботом
- Храните токен в секрете

---

## 3. Настройка settings.py

### Шаг 3.1: Открыть settings.py

```powershell
cd C:\Users\HP_PC\arbitrage-bot
notepad settings.py
# Или используйте VS Code, PyCharm и т.д.
```

### Шаг 3.2: Найти секцию Telegram

Найдите строки (примерно строка 40-45):
```python
# Telegram Bot Configuration
TELEGRAM_BOT_ENABLED = _get_env_bool("ARB_TELEGRAM_ENABLED", False)
TELEGRAM_BOT_TOKEN = os.getenv("ARB_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("ARB_TELEGRAM_CHAT_ID", "")
```

### Шаг 3.3: Включить бота и вставить токен

Измените на:
```python
# Telegram Bot Configuration
TELEGRAM_BOT_ENABLED = _get_env_bool("ARB_TELEGRAM_ENABLED", True)  # ← True!
TELEGRAM_BOT_TOKEN = os.getenv("ARB_TELEGRAM_BOT_TOKEN", "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890")  # ← Ваш токен!
TELEGRAM_CHAT_ID = os.getenv("ARB_TELEGRAM_CHAT_ID", "")  # ← Пока оставить пустым
```

**Замените** `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890` на ваш настоящий токен!

### Шаг 3.4: Сохранить файл

Сохраните `settings.py`

---

## 4. Как Найти Chat ID

### Метод 1: Через @userinfobot (Самый простой)

1. Откройте Telegram
2. Найдите бота: `@userinfobot`
3. Нажмите START
4. Бот отправит ваш Chat ID, например:
   ```
   Id: 123456789
   ```
5. Скопируйте число (это ваш Chat ID)

### Метод 2: Через вашего бота

1. Найдите вашего бота (например, `@my_arbitrage_trading_bot`)
2. Отправьте ему любое сообщение, например: `hello`
3. Откройте браузер и перейдите по ссылке:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
   Замените `<YOUR_TOKEN>` на ваш токен
   
4. В ответе найдите:
   ```json
   {
     "update_id": 123,
     "message": {
       "message_id": 1,
       "from": {
         "id": 123456789,  ← Это ваш Chat ID!
   ```

### Метод 3: Через бота при первом запуске

1. Запустите бота (без Chat ID)
2. Найдите своего бота в Telegram
3. Отправьте `/start`
4. В логах бота увидите:
   ```
   Received message from chat_id: 123456789
   ```
5. Скопируйте Chat ID из логов

### Шаг 4.4: Вставить Chat ID в settings.py

Откройте `settings.py` и измените:
```python
TELEGRAM_CHAT_ID = os.getenv("ARB_TELEGRAM_CHAT_ID", "123456789")  # ← Ваш Chat ID!
```

**Сохраните файл!**

---

## 5. Запуск и Тестирование

### Шаг 5.1: Запустить бота

```powershell
cd C:\Users\HP_PC\arbitrage-bot
python main.py --mode dry-run
```

### Шаг 5.2: Проверить логи

В консоли должно быть:
```
✅ Telegram bot enabled
✅ Telegram Bot initialized
🤖 Telegram: Sent startup notification
```

### Шаг 5.3: Открыть Telegram

1. Откройте Telegram
2. Найдите вашего бота
3. Должно прийти сообщение:
   ```
   🚀 Arbitrage Bot Started!
   
   Mode: DRY_RUN
   Exchanges: 4
   Strategies: 14
   
   Use /help for commands
   ```

### Шаг 5.4: Отправить /start

Отправьте боту:
```
/start
```

Должен ответить с приветствием и списком команд!

---

## 6. Использование Команд

### Доступные Команды:

#### `/start` или `/help`
Показывает список всех команд

**Пример ответа:**
```
🤖 Arbitrage Bot Commands

/start - Show this help
/status - Bot status
/balance - Exchange balances
/trades - Trade statistics
/opportunities - Recent opportunities
/help - Show commands

Bot is running in DRY_RUN mode
```

#### `/status`
Показывает текущий статус бота

**Пример ответа:**
```
📊 Bot Status

Mode: 🔵 DRY_RUN
Uptime: 1h 23m
P&L Today: $45.67 (+12.5%)

WebSocket Status:
✅ Bybit - Connected
✅ KuCoin - Connected
✅ HTX - Connected
✅ MEXC - Connected

Trades Today: 15
Win Rate: 73.3%
```

#### `/balance`
Показывает балансы на всех биржах

**Пример ответа:**
```
💰 Exchange Balances

Bybit:
  USDT: $104.00 (virtual)
  BTC: 0.0003
  
KuCoin:
  USDT: $104.00 (virtual)
  
HTX:
  USDT: $104.00 (virtual)
  
MEXC:
  USDT: $104.00 (virtual)

Total USDT: $416.00
🔵 Virtual balances (DRY_RUN mode)
```

#### `/trades`
Показывает статистику сделок

**Пример ответа:**
```
📈 Trade Statistics

Total Trades: 45
Successful: 33 (73.3%)
Failed: 12 (26.7%)

Profit & Loss:
Total P&L: $125.50
Avg Profit: $2.79 per trade
Best Trade: $15.30
Worst Trade: -$3.20

Win Rate: 73.3%
Sharpe Ratio: 2.45
```

#### `/opportunities`
Показывает недавние возможности

**Пример ответа:**
```
🎯 Recent Opportunities

Last 10 opportunities found:

1. BTC-USDT: 0.15% ROI
   Bybit → KuCoin
   2 minutes ago
   
2. ETH-USDT: 0.12% ROI
   HTX → MEXC
   5 minutes ago

... (more opportunities)
```

---

## 7. Troubleshooting

### Проблема: Бот не отвечает

**Решение:**
1. Проверьте токен в `settings.py`
2. Убедитесь что `TELEGRAM_BOT_ENABLED = True`
3. Перезапустите бота
4. Проверьте логи на ошибки

### Проблема: "Unauthorized" ошибка

**Причина:** Неправильный токен

**Решение:**
1. Проверьте токен в settings.py
2. Убедитесь что скопировали полностью
3. Получите новый токен через /token в @BotFather

### Проблема: Бот отвечает, но не той информацией

**Решение:**
1. Проверьте Chat ID в settings.py
2. Убедитесь что это ваш Chat ID
3. Используйте @userinfobot для проверки

### Проблема: Команды не работают

**Решение:**
1. Отправьте `/start` сначала
2. Команды должны начинаться с `/`
3. Проверьте что бот запущен
4. Проверьте логи бота

### Проблема: Не приходят автоматические обновления

**Причина:** Мониторинг loop может не запуститься

**Решение:**
1. Проверьте логи на ошибки
2. Убедитесь что бот работает > 30 минут
3. Обновления приходят каждые 30 минут

---

## 📊 Примеры Использования

### Мониторинг в течение дня

```
09:00 - Запустить бота
09:01 - /start (проверить что работает)
09:05 - /status (проверить подключения)
10:00 - /balance (проверить балансы)
12:00 - /trades (статистика утренних сделок)
15:00 - /opportunities (новые возможности?)
18:00 - /status (финальная проверка)
```

### Автоматические Обновления

Бот автоматически отправляет:
- Каждые 30 минут: статус обновление
- При новой возможности (ROI > 0.1%)
- При выполнении сделки
- При критических ошибках

---

## 🎯 FAQ

### Q: Могу ли я использовать одного бота для нескольких ботов?
**A:** Нет, создайте отдельного бота для каждого trading бота

### Q: Бот бесплатный?
**A:** Да, создание Telegram ботов бесплатно

### Q: Безопасно ли?
**A:** Да, но не делитесь токеном!

### Q: Могу ли я изменить команды?
**A:** Да, отредактируйте `core/telegram_bot.py`

### Q: Как удалить бота?
**A:** Напишите @BotFather команду `/deletebot`

### Q: Бот работает 24/7?
**A:** Да, если ваш компьютер работает 24/7

---

## ✅ CHECKLIST

- [ ] Создал бота через @BotFather
- [ ] Получил токен
- [ ] Добавил токен в settings.py
- [ ] Включил бота (TELEGRAM_BOT_ENABLED = True)
- [ ] Узнал свой Chat ID
- [ ] Добавил Chat ID в settings.py
- [ ] Сохранил settings.py
- [ ] Запустил бота
- [ ] Получил стартовое сообщение
- [ ] Протестировал /start
- [ ] Протестировал /status
- [ ] Протестировал /balance

---

## 🎉 ГОТОВО!

Теперь ваш Telegram бот полностью настроен и готов к использованию!

**Команды работают:**
- ✅ /start
- ✅ /status
- ✅ /balance
- ✅ /trades
- ✅ /opportunities
- ✅ /help

**Автоматические обновления:**
- ✅ Каждые 30 минут
- ✅ При новых возможностях
- ✅ При сделках

**Удачной торговли!** 💰🚀

---

**Если проблемы - проверьте:**
1. Токен правильный
2. Chat ID правильный
3. TELEGRAM_BOT_ENABLED = True
4. Бот запущен
5. Отправили /start

**Всё работает!** ✅
