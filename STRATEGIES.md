# 📊 Все 14 стратегий арбитражного бота — точное описание

## 🔄 Полный цикл работы бота (от запуска до прибыли)

```
py main.py --mode real

ФАЗА 1 — ИНИЦИАЛИЗАЦИЯ (0-5 секунд):
├─ REST клиенты: Bybit, KuCoin, HTX, MEXC, Binance
├─ Синхронизация серверного времени (sync_server_time для каждой биржи)
├─ Менеджер балансов: запрос реальных балансов всех 5 бирж
├─ Риск-менеджер: MAX_DAILY_LOSS лимит, circuit breaker
├─ Health Monitor: мониторинг ошибок API, latency, error rate

ФАЗА 2 — ПОДКЛЮЧЕНИЕ БИРЖ (5-10 секунд):
├─ WebSocket подключения (real-time bid/ask стриминг):
│  ├─ BybitWS → обновляет PriceStore
│  ├─ KuCoinWS → обновляет PriceStore
│  ├─ HtxWS → обновляет PriceStore
│  ├─ MEXCWS → обновляет PriceStore
│  └─ BinanceWS → обновляет PriceStore
└─ PriceStore: {"NEAR-USDT": {"MEXC": {bid, ask, levels}, "KuCoin": {bid, ask, levels}}}

ФАЗА 3 — СБОР СИГНАЛОВ (неограниченное время):
├─ ArbitrageEngine.scan_once() каждые 0.15-0.5с (быстрые стратегии)
├─ StrategyDispatcher.scan_slow() каждые 5 мин (медленные стратегии)
├─ Каждый найденный спред с ROI > 0 записывается через record_signal()
├─ signal_allocator считает ТОЛЬКО CROSS_EXCHANGE сигналы с ROI > 0
├─ Ждём 15+ таких сигналов для ОДНОЙ монеты (per-symbol)
└─ Score = частота × средний ROI → выбираем лучшую монету

ФАЗА 4 — PRE-FUND (одноразово):
├─ Покупаем выбранную монету на всех 5 биржах (market buy)
├─ Каждая биржа: 50% капитала → монета, 50% → USDT
├─ Нужно успешно купить на ≥2 биржах (MIN_EXCHANGES_FOR_ARB)
├─ LOT_SIZE rounding для Binance, quoteCoin для Bybit, quoteOrderQty для Binance
└─ _initial_setup_done = True → арбитраж начинается

ФАЗА 5 — ТОРГОВЛЯ (бесконечно):
├─ Только 1 сделка за цикл (ONE_TRADE_PER_CYCLE)
├─ Только pre-funded монета (current_coin filter)
├─ Trade lock (asyncio.Lock) — нет параллельных сделок
├─ Проверки перед каждой сделкой:
│  ├─ Спред ≥ total fees (HARD FLOOR)
│  ├─ Спред держится ≥ 500мс (spread persistence)
│  ├─ Latency buy + sell < 1000мс
│  ├─ VWAP slippage < 0.3%
│  ├─ Expected profit ≥ $0.01 (MIN_LIVE_NET_PROFIT)
│  ├─ Exposure per coin < 15%, per exchange < 30%
│  ├─ Risk manager: daily PnL not exceeded
│  └─ Circuit breaker: не сработал
├─ Execution: ПАРАЛЛЕЛЬНЫЕ ордера (buy + sell одновременно)
├─ Partial fill handling: hedge >5% дисбаланса
└─ P&L → risk_manager.record_pnl()

ФАЗА 6 — ЗАЩИТА:
├─ Emergency exit: монета падает ≥3% → мгновенная продажа
├─ Daily loss stop: PnL < -MAX_DAILY_LOSS → пауза до UTC midnight
├─ Coin switching: 10 мин тишины + 3 альтернативы + ≤0.5% потерь
└─ Shutdown: sell_all_to_usdt() → все монеты → USDT
```

---

## 📋 Классификация стратегий

### Стратегии делятся на 2 группы:

| Группа | Стратегии | Количество | Торгуют? |
|--------|-----------|------------|----------|
| **ARB_STRATEGIES** (market-neutral) | CROSS_EXCHANGE, TRIANGULAR, SMART_ORDER, FUNDING_RATE, VOLATILITY_ARB, INDEX_ARB, SPREAD_BETTING, PAIRS_TRADING | 8 | ✅ Могут |
| **DIRECTIONAL_STRATEGIES** | VOLATILITY, MOMENTUM, BREAKOUT, DCA, GRID_TRADING, MARKET_MAKING | 6 | ❌ Только сигналы |

**Реально исполняет сделки только CROSS_EXCHANGE.** Остальные — генерируют сигналы, используемые для:
- Выбора монеты (какая наиболее прибыльная)
- Определения режима рынка (ranging vs trending)
- Оптимизации типа ордера (market vs limit)

---

## 🔥 Стратегия 1: CROSS_EXCHANGE (основная)

**Файл:** `core/arbitrage.py` → `scan_once()`

**Суть:** Находит разницу цен одной монеты на РАЗНЫХ биржах и зарабатывает на спреде.

```
Пример:
  NEAR на MEXC: ask = $1.1500 (можно купить)
  NEAR на KuCoin: bid = $1.1620 (можно продать)
  
  Спред: ($1.1620 / $1.1500 - 1) × 100 = 1.04%
  Комиссии: MEXC 0.05% + KuCoin 0.10% = 0.15%
  Slippage buffer: 0.07% × 2 = 0.14%
  
  Чистый ROI: 1.04% - 0.15% - 0.14% = 0.75%
  На $12: $0.09 прибыль
```

**Этапы:**
1. `scan_once()` → перебирает все пары бирж для каждого символа
2. Рассчитывает spread = sell_bid / buy_ask - 1
3. Вычитает комиссии обеих бирж + global slippage buffer (0.14%)
4. **Spread persistence:** проверяет что спред существует ≥500мс
5. **Latency check:** суммарная задержка до обеих бирж < 1000мс
6. **VWAP check:** simulate_execution_from_book() → если VWAP отклонение > 0.3%, пропуск
7. `execute_arbitrage()` → параллельные ордера buy + sell
8. **Partial fill handling:** если одна сторона заполнена частично → hedge

**Реальный flow:**
```
scan_once() → find spread → check persistence → check latency → check VWAP →
→ exposure caps → risk manager → execute_arbitrage() →
→ parallel orders (buy + sell) → verify fills → record P&L
```

---

## 🔺 Стратегия 2: TRIANGULAR

**Файл:** `core/triangular_arb.py`

**Суть:** Треугольный арбитраж **ВНУТРИ ОДНОЙ БИРЖИ**. Использует 3 торговые пары для получения прибыли.

```
Пример на KuCoin:
  Маршрут: USDT → BTC → ETH → USDT
  
  Шаг 1: Купить BTC за USDT @ $67,877
  Шаг 2: Купить ETH за BTC @ ETH/BTC = 0.0515
  Шаг 3: Продать ETH за USDT @ $3,500
  
  Начало: $100 USDT
  Шаг 1: $100 → 0.001473 BTC
  Шаг 2: 0.001473 BTC → 0.02861 ETH (по implied rate)
  Шаг 3: 0.02861 ETH → $100.13 USDT
  
  Прибыль: $0.13 (0.13%) — 3 × 0.1% комиссий = $0.30
  Результат: -$0.17 (убыток после комиссий)
```

**Этапы:**
1. Строит маршруты из доступных пар (A/USDT + B/USDT → implied A/B)
2. Считает profit = product(rates) - 1 - 3×fee
3. Если profit > 0 после комиссий → генерирует сигнал
4. **Статус:** генерирует сигналы, CROSS_EXCHANGE исполняет если символ совпадает

---

## 📋 Стратегия 3: SMART_ORDER

**Файл:** `core/order_type_selector.py`

**Суть:** Анализирует ширину спреда на биржах и рекомендует оптимальный тип ордера (market vs limit).

```
Пример:
  NEAR-USDT на MEXC: bid=$1.1500, ask=$1.1510
  Спред: 0.087%
  Taker fee: 0.05%
  
  Спред > 2× fee (0.087% > 0.10%)? НЕТ → market order
  Спред > 3× fee (0.087% > 0.15%)? НЕТ → only buy-side limit
```

**Этапы:**
1. Сравнивает bid-ask spread каждой биржи с её taker fee
2. Если spread > 2× fee → limit ордера экономят на комиссиях
3. Если spread > 3× fee → оба ордера limit (maker fee = 0%)
4. **Статус:** подсказка ArbitrageEngine, не исполняет сделки сам

---

## 📊 Стратегия 4: VOLATILITY

**Файл:** `strategies/volatility_arbitrage_strategy.py` → `scan_fast()`

**Суть:** Детекция краткосрочной волатильности. Высокая волатильность = шире спреды = больше арбитражных возможностей.

```
Пример:
  Последние 10 цен NEAR: [1.15, 1.16, 1.14, 1.17, 1.13, ...]
  std = 0.015, mean = 1.15
  Volatility = 0.015/1.15 × 100 = 1.30%
  
  1.30% > 0.15% (min fees) → SIGNAL: high volatility detected
```

**Этапы:**
1. Собирает последние 10 цен из PriceStore
2. Считает std/mean × 100 (нормализованная волатильность)
3. Если > минимальных комиссий → сигнал "рынок активен"
4. **Статус:** DIRECTIONAL — только сигнал, влияет на выбор монеты

---

## 📈 Стратегия 5: GRID_TRADING

**Файл:** `core/strategies/grid_trading.py`

**Суть:** Размещает ордера на покупку ниже текущей цены и на продажу выше (сетка).

```
Пример:
  SMA20 = $1.15
  Текущая цена = $1.14 (-0.87%)
  
  Deviation 0.87% > 0.3% → SIGNAL: price below grid level
  Рекомендация: Buy at $1.14 (ниже среднего)
```

**Этапы:**
1. Рассчитывает SMA20 для каждого символа
2. Сравнивает текущую цену с SMA
3. Если отклонение > 0.3% → генерирует сигнал покупки/продажи
4. **Статус:** DIRECTIONAL — только сигнал, не торгует

---

## 💰 Стратегия 6: DCA (Dollar-Cost Averaging)

**Файл:** `core/strategies/dca_strategy.py`

**Суть:** Покупка при снижении цены ниже среднего (усреднение стоимости).

```
Пример:
  SMA20 = $1.15
  Текущая = $1.135 (-1.3%)
  
  -1.3% > -1.0% (порог) → SIGNAL: Buy at discount
  Рекомендуемая сумма: DCA_AMOUNT ($12)
```

**Этапы:**
1. Рассчитывает SMA20
2. Если текущая цена < SMA20 × 0.99 (на 1%+ ниже) → сигнал покупки
3. **Статус:** DIRECTIONAL — только сигнал, не торгует

---

## 🤝 Стратегия 7: MARKET_MAKING

**Файл:** `core/strategies/market_making.py`

**Суть:** Обнаружение возможностей для маркет-мейкинга (одновременные buy+sell ордера).

```
Пример:
  MEXC best ask: $1.1500
  KuCoin best bid: $1.1620
  
  Cross-exchange spread: 1.04%
  Total fees: 0.15%
  
  1.04% > 0.15% → SIGNAL: market making opportunity
  Inventory skew adjustment: если много NEAR → сдвигаем sell ниже
```

**Этапы:**
1. Сравнивает лучшие bid/ask между биржами
2. Рассчитывает inventory skew (_calculate_inventory_skew)
3. Если spread > sum(fees) → сигнал
4. **Статус:** DIRECTIONAL — сигнал, не торгует напрямую

---

## 👯 Стратегия 8: PAIRS_TRADING

**Файл:** `strategies/pairs_trading_strategy.py`

**Суть:** Статистический арбитраж между коррелированными активами. Торговля на возврат к среднему.

```
Пример:
  BTC/ETH ratio: обычно ~19.37
  Сейчас: 19.85 (ETH underperformed)
  Z-score: +2.3 (выше 2σ)
  
  Rolling correlation: 0.72 > 0.50 (минимум) → пара стабильна
  Cointegration: p-value = 0.02 < 0.05 → коинтеграция ✅
  
  Сигнал: Buy ETH, Sell BTC (ожидаем ratio вернётся к 19.37)
```

**Этапы:**
1. `identify_pairs()` → тест коинтеграции для всех пар
2. `rolling_correlation()` → проверка что корреляция > 0.50 (защита от regime shift)
3. `calculate_zscore()` → z-score текущего spread
4. Если |z| > 2.0 → сигнал (short spread или long spread)
5. **Статус:** ARB — генерирует сигнал, может торговать через dispatcher

---

## ⚖️ Стратегия 9: FUNDING_RATE (Cross-Exchange Premium)

**Файл:** `core/strategies/funding_rate_enhanced.py`

**Суть:** Обнаруживает премиум/дисконт цены монеты на одной бирже относительно среднего по всем биржам.

**⚠️ Важно:** Это НЕ настоящий funding rate арбитраж (spot vs perpetual). Это кросс-биржевой premium arb.

```
Пример:
  NEAR средняя: $1.155 (по 5 биржам)
  NEAR на HTX: $1.162 (+0.61% premium)
  NEAR на MEXC: $1.148 (-0.61% discount)
  
  Deviation > 0.22% (min fees) → SIGNAL
  Торговля: Buy MEXC (дешевле), Sell HTX (дороже)
```

**Этапы:**
1. Считает среднюю цену по всем биржам
2. Для каждой биржи: deviation = (price - avg) / avg
3. Если deviation > sum(taker fees) → сигнал
4. **Статус:** ARB — сигнал, может инициировать торговлю

---

## 📡 Стратегия 10: VOLATILITY_ARB

**Файл:** `core/strategies/volatility_arb.py`

**Суть:** Арбитраж на разнице ШИРИНЫ спреда между биржами (не цены!).

```
Пример:
  MEXC spread: 0.04% (tight)
  HTX spread: 0.15% (wide)
  
  Spread diff: 0.11%
  max/min ratio: 0.15/0.04 = 3.75 > 2.0 ✅
  diff > both fees: 0.11% > max(0.05%, 0.20%) → ❌ (HTX fee too high)
```

**Этапы:**
1. Собирает bid-ask spread с каждой биржи
2. Находит биржу с самым узким и самым широким спредом
3. Если разница > обеих комиссий И ratio > 2× → сигнал
4. **Статус:** ARB — сигнал, implied vol arbitrage

---

## 📍 Стратегия 11: INDEX_ARB

**Файл:** `core/strategies/index_arb.py`

**Суть:** Сравнение цены монеты на каждой бирже с "индексной" (средней) ценой по всем биржам.

```
Пример:
  NEAR индекс (среднее 5 бирж): $1.155
  NEAR на KuCoin: $1.162 (+0.61% overpriced)
  NEAR на MEXC: $1.148 (-0.61% underpriced)
  
  KuCoin deviation 0.61% > 0.22% fees → SIGNAL: sell on KuCoin
  MEXC deviation -0.61% > 0.22% fees → SIGNAL: buy on MEXC
```

**Этапы:**
1. Рассчитывает индексную (среднюю) цену
2. Для каждой биржи: deviation = (price - index) / index
3. Если |deviation| > min required → сигнал
4. **Статус:** ARB — сигнал, по сути аналогичен CROSS_EXCHANGE

---

## 📉 Стратегия 12: SPREAD_BETTING

**Файл:** `core/strategies/spread_betting.py`

**Суть:** Торговля на возврат к среднему СПРЕДА между двумя активами (mean-reversion).

```
Пример:
  BTC-USDT / ETH-USDT spread ratio за 20 периодов:
  Среднее: 0.0525
  Текущее: 0.0548
  Std: 0.0008
  Z-score: (0.0548 - 0.0525) / 0.0008 = +2.875
  
  Z > 2.0 → SIGNAL: spread слишком широкий, ожидаем сжатие
```

**Этапы:**
1. Рассчитывает ratio = price1 / price2 за последние 20 периодов
2. Z-score = (current_ratio - mean) / std
3. Если |z| > 2.0 → сигнал
4. **Статус:** ARB — сигнал, mean-reversion play

---

## 🚀 Стратегия 13: MOMENTUM

**Файл:** `strategies/momentum_strategy.py`

**Суть:** RSI (Relative Strength Index) для обнаружения перекупленности/перепроданности.

```
Пример:
  NEAR последние 15 цен: рост 12 из 15
  RSI = 82 (overbought)
  
  RSI > 70 → SIGNAL: SELL (ожидаем коррекцию)
  Strength: (82-70)/30 = 0.40 > 0.30 (минимум)
```

**Этапы:**
1. Рассчитывает RSI по последним 15 ценам
2. RSI < 30 → buy signal (перепродано)
3. RSI > 70 → sell signal (перекуплено)
4. **Статус:** DIRECTIONAL — только сигнал, НИКОГДА не торгует (конфликт с market-neutral арбитражем)

---

## 🔨 Стратегия 14: BREAKOUT

**Файл:** `strategies/breakout_strategy.py`

**Суть:** Обнаружение пробоя уровней поддержки/сопротивления.

```
Пример:
  NEAR resistance levels: [$1.17, $1.20]
  NEAR support levels: [$1.12, $1.10]
  Текущая цена: $1.175 (+0.43% от resistance $1.17)
  
  Пробой resistance → SIGNAL: BREAKOUT UP
  Strength: 0.43% > 0.2% min → CONFIRMED
```

**Этапы:**
1. Находит локальные минимумы (support) и максимумы (resistance) за 50 периодов
2. Если цена пробивает уровень на > 0.2% → сигнал
3. **Статус:** DIRECTIONAL — только сигнал, не торгует

---

## 🛡️ Система защиты (все реализовано):

| Защита | Параметр | Файл |
|--------|----------|------|
| Hard fee floor | spread > total_fees | arbitrage.py |
| Spread persistence | ≥500мс | arbitrage.py |
| Latency check | buy+sell < 1000мс | arbitrage.py |
| VWAP slippage | < 0.3% | arbitrage.py |
| Global slippage buffer | 0.07% × 2 ноги | settings.py |
| Min profit | ≥ $0.01 net | order_executor.py |
| Max slippage | ≤ 0.2% | order_executor.py |
| Per-coin exposure | ≤ 15% капитала | order_executor.py |
| Per-exchange exposure | ≤ 30% капитала | order_executor.py |
| Inventory skew | ≤ $20 дисбаланс | settings.py |
| Daily loss stop | MAX_DAILY_LOSS | risk_manager.py |
| Circuit breaker | проверка каждый цикл | arbitrage.py |
| Partial fill hedge | >5% дисбаланса | order_executor.py |
| Emergency exit | монета -3% | signal_allocator.py |
| Rate limiting | per-exchange | rate_limiter.py |
| Exchange health | error rate + latency | health_monitor.py |
| Sell all on shutdown | Ctrl+C → USDT | main.py |
| Rolling correlation | pairs corr > 0.50 | pairs_trading_strategy.py |
| Cointegration test | p-value < 0.05 | pairs_trading_strategy.py |
| Trade lock | asyncio.Lock | order_executor.py |
| One trade per cycle | engine_trade_this_cycle | arbitrage.py |
| Strategy separation | ARB vs DIRECTIONAL | settings.py |
