# Environment Variables Guide

This guide covers all environment variables used by the Arbitrage Bot.

## 🔐 API Credentials

### Exchange API Keys
Set these for live trading (required when `DRY_RUN=False`):

```bash
# Bybit
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here

# KuCoin (requires passphrase)
KUCOIN_API_KEY=your_api_key_here
KUCOIN_API_SECRET=your_api_secret_here
KUCOIN_API_PASSPHRASE=your_passphrase_here

# HTX (Huobi)
HTX_API_KEY=your_api_key_here
HTX_API_SECRET=your_api_secret_here

# XT.COM
XT_API_KEY=your_api_key_here
XT_API_SECRET=your_api_secret_here

# MEXC
MEXC_API_KEY=your_api_key_here
MEXC_API_SECRET=your_api_secret_here
```

### Telegram Notifications
Optional but recommended for monitoring:

```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

Get these by:
1. Create bot with [@BotFather](https://t.me/botfather)
2. Get chat ID from [@userinfobot](https://t.me/userinfobot)

## ⚙️ Trading Configuration

### Execution Mode
```bash
# Safe mode (default) - simulates all trades
ARB_DRY_RUN=True

# Live mode - REAL TRADING! Use with caution
ARB_DRY_RUN=False
```

### Risk Parameters
```bash
# Minimum net ROI to execute trade (default: 0.03%)
ARB_MIN_NET_ROI_PCT=0.03

# Maximum exposure per trade in USDT (default: $200)
ARB_MAX_EXPOSURE_USDT=200.0

# Safety factor for liquidity (default: 0.5 = use 50% of available)
ARB_SAFETY_FACTOR=0.5

# Maximum trades per minute (default: 30)
ARB_MAX_TRADES_PER_MINUTE=30

# Cooldown between trades on same symbol in seconds (default: 3.0)
ARB_SYMBOL_COOLDOWN_SEC=3.0

# Maximum concurrent opportunities to process (default: 3)
ARB_MAX_CONCURRENT_OPPS=3
```

### Performance Settings
```bash
# Scan interval in seconds (default: 0.1)
ARB_SCAN_INTERVAL_SEC=0.1

# Monitoring output interval (default: 5.0)
ARB_MONITOR_INTERVAL_SEC=5.0

# Enable event-driven scanning (default: True)
ARB_EVENT_DRIVEN_SCAN=True

# Minimum interval between scans of same symbol (default: 0.5)
ARB_MIN_SCAN_INTERVAL_PER_SYMBOL=0.5
```

### WebSocket Settings
```bash
# Auto-reconnect on disconnect (default: True)
ARB_WS_AUTO_RECONNECT=True

# Initial reconnect delay in seconds (default: 5.0)
ARB_WS_RECONNECT_DELAY=5.0

# Maximum reconnect delay (default: 300.0)
ARB_WS_MAX_RECONNECT_DELAY=300.0

# Backoff multiplier (default: 2.0)
ARB_WS_BACKOFF_MULTIPLIER=2.0

# Maximum reconnect attempts (0 = unlimited, default: 0)
ARB_WS_MAX_RECONNECT_ATTEMPTS=0

# Stream staleness threshold in seconds (default: 60.0)
ARB_STREAM_STALENESS_SEC=60.0

# Health check interval (default: 30.0)
ARB_HEALTH_CHECK_INTERVAL=30.0
```

## 🛡️ Risk Management

### Risk Limits
```bash
# Maximum daily loss as percentage of capital (default: 2.0%)
ARB_MAX_DAILY_LOSS_PCT=2.0

# Maximum single trade size as percentage of capital (default: 5.0%)
ARB_MAX_SINGLE_TRADE_PCT=5.0

# Maximum drawdown before pause (default: 10.0%)
ARB_MAX_DRAWDOWN_PCT=10.0

# Maximum exposure per exchange as percentage (default: 30.0%)
ARB_MAX_EXPOSURE_PER_EXCHANGE_PCT=30.0
```

## 📊 Data & Logging

### Trading Pairs
```bash
# Comma-separated list of symbols (default: top 10 pairs)
ARB_SYMBOLS=BTC-USDT,ETH-USDT,SOL-USDT,BNB-USDT,XRP-USDT
```

### Order Book Settings
```bash
# Number of orderbook levels to consider (default: 20)
ARB_ORDERBOOK_TOP_K=20

# Default quantity fallback (default: 0.001)
ARB_DEFAULT_QUANTITY=0.001
```

### Persistence
```bash
# CSV file for opportunities (default: arbs.csv)
ARB_OPPORTUNITIES_CSV=arbs.csv

# Log level (default: INFO)
ARB_LOG_LEVEL=INFO
# Options: DEBUG, INFO, WARNING, ERROR
```

## 📝 Example .env File

Create a `.env` file in the project root:

```bash
# ======================
# TRADING MODE
# ======================
ARB_DRY_RUN=True

# ======================
# API CREDENTIALS
# ======================
BYBIT_API_KEY=your_key
BYBIT_API_SECRET=your_secret

KUCOIN_API_KEY=your_key
KUCOIN_API_SECRET=your_secret
KUCOIN_API_PASSPHRASE=your_passphrase

# Add other exchanges as needed...

# ======================
# TELEGRAM NOTIFICATIONS
# ======================
TELEGRAM_BOT_TOKEN=1234567890:ABC...
TELEGRAM_CHAT_ID=123456789

# ======================
# RISK PARAMETERS
# ======================
ARB_MIN_NET_ROI_PCT=0.03
ARB_MAX_EXPOSURE_USDT=200.0
ARB_MAX_DAILY_LOSS_PCT=2.0
ARB_MAX_SINGLE_TRADE_PCT=5.0

# ======================
# PERFORMANCE
# ======================
ARB_SCAN_INTERVAL_SEC=0.1
ARB_MAX_TRADES_PER_MINUTE=30
ARB_SYMBOL_COOLDOWN_SEC=3.0

# ======================
# LOGGING
# ======================
ARB_LOG_LEVEL=INFO
```

## 🚀 Quick Start

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your settings

3. Test in dry-run mode:
   ```bash
   python main.py
   ```

4. When ready for live trading:
   - Set `ARB_DRY_RUN=False` in `.env`
   - Start with small `ARB_MAX_EXPOSURE_USDT`
   - Monitor closely via Telegram

## ⚠️ Safety Warnings

1. **Never share API keys** - Store in `.env`, add to `.gitignore`
2. **Start with dry-run** - Test thoroughly before live trading
3. **Use API restrictions** - Limit API keys to trading only, no withdrawals
4. **Monitor actively** - Use Telegram notifications
5. **Start small** - Use low `ARB_MAX_EXPOSURE_USDT` initially
6. **Check balances** - Ensure sufficient funds on all exchanges

## 📚 Additional Resources

- [Bybit API Docs](https://bybit-exchange.github.io/docs/v5/intro)
- [KuCoin API Docs](https://docs.kucoin.com/)
- [HTX API Docs](https://www.htx.com/en-us/opend/newApiPages/)
- [XT.COM API Docs](https://doc.xt.com/)
- [MEXC API Docs](https://mexcdevelop.github.io/apidocs/)

## 🆘 Troubleshooting

### Bot won't start
- Check `.env` file exists and is readable
- Verify API keys are valid
- Check logs for specific errors

### No opportunities detected
- Ensure all exchanges are connected (check logs)
- Lower `ARB_MIN_NET_ROI_PCT` temporarily
- Check that symbols are listed on multiple exchanges

### High CPU usage
- Increase `ARB_SCAN_INTERVAL_SEC`
- Reduce number of trading symbols
- Disable `ARB_EVENT_DRIVEN_SCAN`

### Trade execution failures
- Verify API keys have trading permissions
- Check account balances on exchanges
- Ensure API rate limits not exceeded
