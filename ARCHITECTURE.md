# 🏗️ ПОЛНАЯ АРХИТЕКТУРА БОТА — ОТ ЗАПУСКА ДО ПРИБЫЛИ

## ОГЛАВЛЕНИЕ
1. [Обзор архитектуры](#1-обзор-архитектуры)
2. [Фаза 1: Запуск (0-10с)](#2-фаза-1-запуск)
3. [Фаза 2: Сбор данных (WebSocket)](#3-фаза-2-сбор-данных)
4. [Фаза 3: Сканирование (150мс цикл)](#4-фаза-3-сканирование)
5. [Фаза 4: Исполнение (Maker-First)](#5-фаза-4-исполнение)
6. [Фаза 5: Контроль после сделки](#6-фаза-5-контроль)
7. [Фаза 6: Завершение работы](#7-фаза-6-завершение)
8. [Стратегии: что работает и что нет](#8-стратегии)
9. [Что лишнее в боте](#9-что-лишнее)
10. [Ожидаемый профит](#10-профит)

---

## 1. ОБЗОР АРХИТЕКТУРЫ

```
main.py: IntegratedArbitrageBot
├── 5× REST клиентов (Binance, MEXC, KuCoin, Bybit, HTX)
├── 5× WebSocket подключений (orderbook + trades)
├── ArbitrageEngine (scan_once) — основной сканер
├── StrategyDispatcher (scan_fast + scan_slow) — 14 стратегий
├── OrderExecutor (maker-first) — исполнение
├── CapitalManager (4 уровня) — адаптивный размер позиции
├── SignalAllocator — выбор монеты для pre-fund
├── RiskManager — контроль убытков
├── StateManager — сохранение состояния
└── BalanceManager — отслеживание балансов
```

### Ключевые файлы:
| Файл | Строк | Назначение |
|------|-------|------------|
| `main.py` | ~2073 | Оркестратор: запуск, циклы, shutdown |
| `core/arbitrage.py` | ~1241 | Сканер: VWAP, spread, CROSS_EXCHANGE |
| `core/order_executor.py` | ~753 | Исполнение: maker-first, partial fill |
| `core/capital_manager.py` | ~378 | Уровни капитала, kill-logic, threshold |
| `core/signal_allocator.py` | ~1039 | Выбор монеты, pre-fund, ребаланс |
| `core/strategy_dispatcher.py` | ~925 | 14 стратегий: fast + slow scan |
| `settings.py` | ~508 | Все настройки и параметры |

---

## 2. ФАЗА 1: ЗАПУСК (0-10 секунд)

### 2.1 REST подключение
```python
# Для каждой из 5 бирж:
1. Создание REST клиента с API ключами из .env
2. sync_server_time() — синхронизация часов
3. get_balance() — получение баланса USDT
4. Загрузка exchange_config: maker/taker fee, min_notional, step_size
```

### 2.2 Биржевые параметры (exchange_config.py)
```
Bybit:   maker=0.10%, taker=0.10%
KuCoin:  maker=0.10%, taker=0.10%
HTX:     maker=0.20%, taker=0.20%  ← самая дорогая
MEXC:    maker=0.00%, taker=0.05%  ← самая дешёвая (maker FREE!)
Binance: maker=0.10%, taker=0.10%
```

### 2.3 WebSocket подключение
```python
# Для каждой биржи:
1. Подключение к orderbook stream (depth 10-20 уровней)
2. Подключение к trades stream
3. Данные → PriceStore (хранилище цен в реальном времени)
```

### 2.4 Восстановление состояния
```python
1. state_manager.load_state() — загрузка из bot_state.json
2. Восстановление: daily_pnl, lifetime_pnl, consecutive_losses
3. Проверка orphaned orders → cancel если старые (>5 мин)
4. Восстановление RiskManager counters
```

### 2.5 Выбор уровня капитала (CapitalManager)
```
$0-150:   Level 1 MicroArb   — 1 монета, 1 параллельная сделка
$150-300: Level 2 MultiCoin  — 3 монеты, 3 параллельных сделки
$300-1000: Level 3 StatArb   — 5 монет, 5 параллельных сделок
$1000+:   Level 4 MarketMaking — 6 монет, 8 параллельных сделок
```

---

## 3. ФАЗА 2: СБОР ДАННЫХ

### PriceStore — центральное хранилище
```python
# Формат данных:
store[symbol][exchange] = {
    "bid": 1.1600,    # лучшая цена покупки
    "ask": 1.1500,    # лучшая цена продажи
    "bid_size": 100,  # объём на лучшем bid
    "ask_size": 200,  # объём на лучшем ask
    "bids_levels": [(1.16, 100), (1.159, 50), ...],  # глубина
    "asks_levels": [(1.15, 200), (1.151, 80), ...],
    "ts": 1709355123.456  # timestamp обновления
}
```

### Проверки качества данных:
- **Staleness**: если `ts` > 200ms старый → данные отброшены
- **Flash crash**: если цена упала >5% за 1 минуту → стоп-торговля
- **Wash trading**: фильтрация подозрительных объёмов

---

## 4. ФАЗА 3: СКАНИРОВАНИЕ (каждые 150мс)

### 4.1 ArbitrageEngine.scan_once() — ОСНОВНОЙ ЦИКЛ

```python
for symbol in 19_symbols:  # BTC, ETH, SOL, XRP, ...
    for (buy_exchange, sell_exchange) in all_pairs:  # 5×4=20 пар
        
        # 1. Проверка свежести данных (<200мс)
        if orderbook_age > 200ms: skip
        
        # 2. Kill-logic: монета/биржа отключена?
        if not capital_manager.is_coin_enabled(symbol): skip
        if not capital_manager.is_exchange_enabled(exchange): skip
        
        # 3. Быстрый расчёт спреда (top-of-book)
        spread = (sell_bid - buy_ask) / buy_ask × 100%
        
        # 4. MAKER-FIRST fee optimization:
        #    Buy fee = MAKER (limit order)
        #    Sell fee = TAKER (market order)
        #    MEXC buy → 0% fee! (вместо 0.05% taker)
        buy_fee = exchange_params[buy_ex]["maker"]  # 0% для MEXC!
        sell_fee = exchange_params[sell_ex]["taker"]
        
        # 5. Динамический порог (Engine 2.0):
        threshold = fees + level_cushion + latency_risk + volatility_buffer
        if spread < threshold: skip  # не прибыльно
        
        # 6. HTX фильтр: используем только при широких спредах
        if HTX involved and spread < htx_min_spread: skip
        
        # 7. Spread persistence (спред живёт >150-180мс?)
        if spread_first_seen < 150ms ago: skip  # может исчезнуть
        
        # 8. VWAP симуляция (глубина стакана)
        vwap_buy = weighted_avg_price(buy_side_levels, qty)
        vwap_sell = weighted_avg_price(sell_side_levels, qty)
        real_spread = vwap_sell / vwap_buy - 1
        if vwap_slippage > 0.3%: skip
        
        # 9. Размер позиции (adaptive)
        qty = min(35% × balance, 70% × depth, exposure_limit)
             × compound_multiplier × volatility_adjustment
        
        # 10. Финальная проверка: net_profit > $0.01?
        if net_profit < MIN_LIVE_NET_PROFIT: skip
        
        # ✅ OPPORTUNITY FOUND → execute
```

### 4.2 StrategyDispatcher — параллельные стратегии

**Быстрый scan (каждые 150мс):**
- `CROSS_EXCHANGE` — обрабатывается в ArbitrageEngine
- `TRIANGULAR` — треугольный арбитраж (BTC/ETH/SOL пары)
- `SMART_ORDER` — оптимальный маршрут для пар бирж

**Медленный scan (каждые 60с):**
- `FUNDING_RATE` — кросс-биржевая premium/discount
- `INDEX_ARB` — индексный арбитраж
- `VOLATILITY_ARB` — разница spread между биржами
- `PAIRS_TRADING` — коинтегрированные пары
- `SPREAD_BETTING` — статистический спред

**Отключённые (directional — не создают arb edge):**
- ~~VOLATILITY~~ — только наблюдение
- ~~MOMENTUM~~ — RSI тренд (не arb)
- ~~BREAKOUT~~ — пробой уровней (не arb)
- ~~DCA~~ — усреднение (не arb)
- ~~GRID_TRADING~~ — сетка (не arb)
- ~~MARKET_MAKING~~ — наблюдение спреда

---

## 5. ФАЗА 4: ИСПОЛНЕНИЕ (Maker-First Model)

### 5.1 Поток исполнения
```
OPPORTUNITY → OrderExecutor.execute_arbitrage()
  │
  ├─ Risk check (daily loss, exposure caps)
  ├─ Balance check (enough USDT/coins?)
  ├─ Volume sanity (qty > 0, notional > $5?)
  │
  ├─ STEP 1: Limit BUY на дешёвой бирже
  │   price = best_bid + 20% от спреда
  │   timeout = 250мс
  │   min_fill = 75%
  │
  ├─ STEP 2: Ожидание fill (user data stream)
  │   if fill ≥ 75% → STEP 3
  │   if timeout → cancel
  │
  ├─ STEP 3: Market SELL на дорогой бирже
  │   qty = filled_amount
  │   execution < 200мс
  │
  └─ STEP 4: Partial fill hedge
      if buy=100%, sell=92%
      → hedge 8% market order opposite side
```

### 5.2 Maker-First fee advantage
```
РАНЬШЕ (market + market):
  Buy MEXC taker:  0.05%
  Sell KuCoin taker: 0.10%
  ИТОГО: 0.15%

ТЕПЕРЬ (limit + market):
  Buy MEXC maker:  0.00%  ← БЕСПЛАТНО!
  Sell KuCoin taker: 0.10%
  ИТОГО: 0.10%  ← экономия 0.05% на каждой сделке!
```

### 5.3 Trade Lock
```python
async with self._trade_lock:  # asyncio.Lock
    # Только 1 сделка одновременно
    # Предотвращает race condition на балансе
```

---

## 6. ФАЗА 5: КОНТРОЛЬ ПОСЛЕ СДЕЛКИ

### 6.1 PnL фиксация
```python
real_pnl = received_usdt - spent_usdt - fees
capital_manager.record_trade_result(
    symbol, roi_pct, total_slippage, buy_exchange, sell_exchange)
```

### 6.2 Kill-logic
```python
# 3 убытка подряд → монета отключена на 2 часа
if consecutive_losses[symbol] >= 3:
    disable_coin(symbol, duration=2h)

# Средний slippage > 0.35% → биржа отключена на 1 час  
if avg_slippage[exchange] > 0.35%:
    disable_exchange(exchange, duration=1h)
```

### 6.3 Circuit Breaker
```python
if daily_loss > MAX_DAILY_LOSS (10% капитала):
    → СТОП до UTC midnight
```

### 6.4 Exchange Quality Ranking
```python
# Каждые 100 сделок:
score = winrate × avg_profit / max(avg_slippage, 0.01)
# Худшая биржа понижается в приоритете
```

### 6.5 Overtrading Control
```python
if avg_net_profit_last_10 < 0.2%:
    → повысить threshold на 0.05% (торговать реже, но прибыльнее)
```

---

## 7. ФАЗА 6: ЗАВЕРШЕНИЕ (Ctrl+C)

```python
1. cancel_all_open_orders()  # Отмена всех лимитных ордеров
2. sell_all_to_usdt()        # Продажа ВСЕХ монет в USDT
3. state_manager.save_state() # Сохранение PnL, losses, etc.
4. Закрытие REST + WS соединений
```

---

## 8. СТРАТЕГИИ: ЧТО РАБОТАЕТ И ЧТО НЕТ

### ✅ АКТИВНЫЕ (создают real edge):

| # | Стратегия | Тип | Когда прибыльна | Min spread |
|---|-----------|-----|-----------------|------------|
| 1 | **CROSS_EXCHANGE** | Fast | Всегда (основная) | >fees+0.18% |
| 2 | **TRIANGULAR** | Fast | При расхождении пар | >4×fee |
| 3 | **SMART_ORDER** | Fast | При широком спреде | >0.10% |
| 4 | **FUNDING_RATE** | Slow | При premium >0.1% | >0.10% |
| 5 | **INDEX_ARB** | Slow | При deviation >0.1% | >0.10% |
| 6 | **VOLATILITY_ARB** | Slow | При разнице spread | >0.10% |
| 7 | **PAIRS_TRADING** | Slow | При z-score >2.0 | depends |
| 8 | **SPREAD_BETTING** | Slow | При z-score >2.0 | depends |

### 🚫 ОТКЛЮЧЁННЫЕ (не создают arb edge, тратят CPU):

| # | Стратегия | Почему отключена |
|---|-----------|-----------------|
| 9 | VOLATILITY | Только наблюдение, нет executable trade |
| 10 | MOMENTUM | Directional (RSI), конфликтует с arb |
| 11 | BREAKOUT | Directional (пробой), конфликтует с arb |
| 12 | DCA | Buy-the-dip, не cross-exchange |
| 13 | GRID_TRADING | Сетка позиций, не cross-exchange |
| 14 | MARKET_MAKING | Наблюдение спреда, не executable |

---

## 9. ЧТО ЛИШНЕЕ В БОТЕ

### Файлы которые НЕ используются (50+ файлов):
Большинство файлов в `professional_features/`, `analytics/`, `ml/` — это **stub-модули** которые:
- Импортируются в main.py
- Создаются как объекты
- **Никогда не вызываются** в execution path

### Конкретно лишнее:
| Модуль | Почему лишний |
|--------|--------------|
| `professional_features/sentiment_analyzer.py` | Не импортируется нигде |
| `professional_features/smart_order_router.py` | Не импортируется нигде |
| `professional_features/tape_reader.py` | Не импортируется нигде |
| `analytics/report_generator.py` | Не импортируется нигде |
| `analytics/advanced_charting.py` | Не импортируется нигде |
| `ml/pattern_recognition.py` | Импортируется но не используется |
| `ml/ml_model_trainer.py` | Импортируется но не используется |
| 6 directional strategies | Сканируются но ВСЕГДА заблокированы |

### Что НЕ лишнее (критически важное):
- `ArbitrageEngine` — основной сканер
- `OrderExecutor` — исполнение
- `CapitalManager` — уровни + kill-logic
- `SignalAllocator` — выбор монеты
- `RiskManager` — контроль убытков
- `StateManager` — восстановление после краша
- `BalanceManager` — отслеживание баланса
- `ExchangeConfig` — комиссии и LOT_SIZE
- 5× REST клиентов + 5× WebSocket

---

## 10. ОЖИДАЕМЫЙ ПРОФИТ

### Математика при $72 капитале:
```
Капитал на бирже: $72 / 5 = $14.40
Working capital: $14.40 × 85% = $12.24
Position per trade: $12.24 × 35% = $4.28

Лучший случай (MEXC buy → Binance sell):
  Buy fee:  0.00% (MEXC maker)
  Sell fee: 0.10% (Binance taker)
  Total:    0.10%
  
  Spread needed: >0.10% + 0.18% cushion = 0.28%
  Net on $4.28 trade: $4.28 × 0.10% = $0.004 per trade
```

### Реальные ожидания:
| Рынок | Спреды | Сделок/день | Профит/день |
|-------|--------|-------------|-------------|
| Спокойный | <0.15% | 0 (ПРАВИЛЬНО!) | $0 |
| Средний | 0.20-0.40% | 3-8 | $0.01-0.06 |
| Волатильный | 0.40-1.0% | 10-30 | $0.10-0.60 |
| Экстремальный | >1.0% | 30+ | $0.50+ |

### Как увеличить профит без увеличения риска:
1. **Увеличить капитал** — профит линейно растёт с капиталом
2. **VIP статус** — снижение комиссий → больше прибыльных спредов
3. **Maker-first на всех биржах** — экономия 0.05-0.10% per trade
4. **MEXC как primary buy exchange** — 0% maker fee
5. **Exclude HTX** — высокие комиссии (0.20%) снижают edge
