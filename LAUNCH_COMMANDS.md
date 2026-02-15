# 🚀 Quick Download and Launch Commands

## 🚨 IMPORTANT! Download the CORRECT branch

**With regular `git clone` you get the basic version (51 files).**
**For the FULL version with all improvements (244 files) use:**

```bash
# ✅ CORRECT - Full version with all improvements
git clone -b copilot/fix-bot-start-issues https://github.com/tsepper002/arbitrage-bot.git

# ❌ WRONG - Basic version without improvements
# git clone https://github.com/tsepper002/arbitrage-bot.git
```

📄 **More details:** [КАК_ПОЛУЧИТЬ_ПОЛНУЮ_ВЕРСИЮ.md](КАК_ПОЛУЧИТЬ_ПОЛНУЮ_ВЕРСИЮ.md)

---

## Download and Install (copy commands one by one)

### Windows (PowerShell/CMD):
```powershell
# 1. Download the bot (FULL VERSION)
git clone -b copilot/fix-bot-start-issues https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run in test mode (safe, no real trading)
python main.py
```

### Linux/macOS:
```bash
# 1. Download the bot (FULL VERSION)
git clone -b copilot/fix-bot-start-issues https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Run in test mode (safe, no real trading)
python3 main.py
```

---

## What You Get in Full Version

### Basic version (main) - 51 files ❌
- Only basic arbitrage
- Minimal functionality

### Full version (copilot/fix-bot-start-issues) - 244 files ✅
- EVERYTHING from basic + 193 additional files:
  - 70+ advanced modules
  - 80+ documentation files
  - Risk & balance management
  - Telegram notifications
  - ML modules & GPU acceleration
  - Multiple trading strategies
  - REST API for all exchanges
  - Advanced monitoring

---

## Quick Setup for Real Trading

### Step 1: Create configuration
```bash
# Windows
copy .env.example .env

# Linux/macOS
cp .env.example .env
```

### Step 2: Open configuration file
```bash
# Windows
notepad .env

# Linux/macOS
nano .env
# or
vim .env
```

### Step 3: Minimum configuration (paste into .env)
```bash
# ========== REQUIRED: API KEYS ==========
# Get from exchange websites in API Management section

# Bybit
ARB_BYBIT_KEY=your_bybit_key
ARB_BYBIT_SECRET=your_bybit_secret

# KuCoin (PASSPHRASE required!)
ARB_KUCOIN_KEY=your_kucoin_key
ARB_KUCOIN_SECRET=your_kucoin_secret
ARB_KUCOIN_PASSPHRASE=your_kucoin_passphrase

# HTX (Huobi)
ARB_HTX_KEY=your_htx_key
ARB_HTX_SECRET=your_htx_secret

# MEXC
ARB_MEXC_KEY=your_mexc_key
ARB_MEXC_SECRET=your_mexc_secret

# ========== OPERATION MODE ==========
# true = test mode (safe, no real trades)
# false = live mode (CAUTION! real trading!)
ARB_DRY_RUN=true

# ========== RISK LIMITS (IMPORTANT!) ==========
ARB_MAX_DAILY_LOSS=50.0          # Max daily loss ($)
ARB_MAX_HOURLY_LOSS=20.0         # Max hourly loss ($)
ARB_MAX_EXPOSURE_USDT=500.0      # Max position size ($)
ARB_MIN_NET_ROI_PCT=0.03         # Min profit for trade (%)
```

### Step 4: Launch the bot
```bash
# Windows
python main.py

# Linux/macOS
python3 main.py
```

---

## Important Commands

### Check configuration:
```bash
python settings.py
```

### Stop the bot:
```
Press Ctrl+C
```

### View logs:
```bash
# Windows
type arbitrage_bot.log

# Linux/macOS
cat arbitrage_bot.log
tail -f arbitrage_bot.log  # Real-time
```

### View trades:
```bash
# Windows
type trades.csv

# Linux/macOS
cat trades.csv
```

---

## Getting API Keys

### Bybit:
```
1. https://www.bybit.com/app/user/api-management
2. Create new API key
3. Permissions: "Trade", "Read Account"
4. NO withdrawal permissions!
```

### KuCoin:
```
1. https://www.kucoin.com/account/api
2. Create new API key
3. Permissions: "General" (read), "Trade"
4. IMPORTANT: Create and remember Passphrase!
5. NO withdrawal permissions!
```

### HTX (Huobi):
```
1. https://www.htx.com/en-us/account/api-management
2. Create new API key
3. Permissions: "Trade", "Read"
4. NO withdrawal permissions!
```

### MEXC:
```
1. https://www.mexc.com/user/openapi
2. Create new API key
3. Permissions: "Spot Trading"
4. NO withdrawal permissions!
```

### Binance (optional):
```
1. https://www.binance.com/en/my/settings/api-management
2. Create new API key
3. Permissions: "Enable Spot & Margin Trading"
4. NO withdrawal permissions!
```

---

## Auto-start (24/7)

### Windows - Auto-start on system boot:

#### Option 1: Watchdog script (recommended)
```powershell
# In PowerShell as Administrator
cd path\to\arbitrage-bot
.\watchdog.ps1
```

#### Option 2: Windows Task Scheduler
```powershell
# 1. Open Task Scheduler
Win+R → taskschd.msc → Enter

# 2. Create new task:
Action → Create Task
Name: Arbitrage Bot
Trigger: At log on
Action: Start a program
  Program: python.exe
  Arguments: main.py
  Working directory: C:\path\to\arbitrage-bot
Conditions: ✓ Start regardless of power
```

### Linux - Systemd service:
```bash
# 1. Create service
sudo nano /etc/systemd/system/arbitrage-bot.service

# 2. Paste configuration:
[Unit]
Description=Crypto Arbitrage Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/arbitrage-bot
ExecStart=/usr/bin/python3 /path/to/arbitrage-bot/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# 3. Start service
sudo systemctl daemon-reload
sudo systemctl enable arbitrage-bot
sudo systemctl start arbitrage-bot

# 4. Check status
sudo systemctl status arbitrage-bot

# 5. View logs
sudo journalctl -u arbitrage-bot -f
```

---

## Telegram Notifications (optional)

### Setup in 2 minutes:

#### 1. Create Telegram bot:
```
1. Open Telegram
2. Find @BotFather
3. Send: /newbot
4. Give bot a name
5. Get token (looks like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)
```

#### 2. Get Chat ID:
```
1. Find @userinfobot in Telegram
2. Press Start
3. Get your Chat ID (number, e.g.: 987654321)
```

#### 3. Add to .env:
```bash
ARB_TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ARB_TELEGRAM_CHAT_ID=987654321
```

#### 4. Restart bot:
```bash
python main.py
```

You'll now receive trade notifications in Telegram!

---

## Troubleshooting

### Error: ModuleNotFoundError
```bash
# Solution: install dependencies
pip install -r requirements.txt

# Or individually:
pip install aiohttp websockets websocket-client requests ccxt psutil cryptography python-dotenv
```

### Error: Authentication failed
```bash
# Check:
1. API keys correctly copied to .env
2. No extra spaces at start/end
3. Keys are active on exchange
4. API permissions include "Trade" and "Read"
```

### Bot doesn't find arbitrage
```bash
# This is normal! Arbitrage is rare.
# Lower threshold in .env:
ARB_MIN_NET_ROI_PCT=0.01  # was 0.03

# Or add more trading pairs in settings.py
```

### WebSocket won't connect
```bash
# Check:
1. Internet connection is stable
2. Antivirus/firewall not blocking
3. VPN disabled (some exchanges block VPN)
4. Try with mobile internet
```

### Bot lags/hangs on Windows 11
```powershell
# Run optimization (as Administrator):
.\optimize_windows11.ps1

# Restart computer
Restart-Computer
```

---

## Security

### ✅ Before Launch:
- [ ] ALWAYS start with `ARB_DRY_RUN=true`
- [ ] Set risk limits (MAX_DAILY_LOSS, MAX_EXPOSURE)
- [ ] Start with small amounts ($50-100)
- [ ] Don't give API keys withdrawal permissions
- [ ] Don't publish .env file

### ⚠️ For Real Trading:
- [ ] Test 24-48 hours in DRY_RUN with real keys
- [ ] Start with $10-20 per exchange
- [ ] Monitor balances for first 2 days
- [ ] Check Telegram notifications
- [ ] Analyze all trades

### 🛡️ Continuous Monitoring:
- [ ] Check logs every 12 hours
- [ ] Monitor P&L (profit/loss)
- [ ] Check position sizes
- [ ] Monitor exchange fees
- [ ] Watch balances on exchanges

---

## Useful Links

### Documentation:
- 📖 [README.md](README.md) - Main documentation
- 📖 [БЫСТРЫЙ_СТАРТ.md](БЫСТРЫЙ_СТАРТ.md) - Quick start in 5 minutes (Russian)
- 📖 [ИНСТРУКЦИЯ.md](ИНСТРУКЦИЯ.md) - Full guide (Russian)
- 📖 [ГДЕ_ВВОДИТЬ_КЛЮЧИ.md](ГДЕ_ВВОДИТЬ_КЛЮЧИ.md) - Where to enter API keys (Russian)

### Exchanges:
- 🏦 [Bybit](https://www.bybit.com)
- 🏦 [KuCoin](https://www.kucoin.com)
- 🏦 [HTX](https://www.htx.com)
- 🏦 [MEXC](https://www.mexc.com)
- 🏦 [Binance](https://www.binance.com)

### GitHub:
- 💻 [Repository](https://github.com/tsepper002/arbitrage-bot)
- 🐛 [Create Issue](https://github.com/tsepper002/arbitrage-bot/issues)

---

## Checklist

### Before First Launch:
- [ ] Git installed
- [ ] Python 3.9+ installed
- [ ] Code downloaded
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] .env file created
- [ ] API keys obtained (minimum 2 exchanges)
- [ ] API keys added to .env
- [ ] `ARB_DRY_RUN=true` set
- [ ] Risk limits configured

### First Launch:
- [ ] Run: `python main.py`
- [ ] Check exchange connections
- [ ] Wait for first data in logs
- [ ] Stop (Ctrl+C)
- [ ] Check logs for errors

### Before Real Trading:
- [ ] Tested 24+ hours in DRY_RUN
- [ ] All connections working
- [ ] Telegram configured and working
- [ ] Small amounts on exchanges ($50-100)
- [ ] Risk limits set
- [ ] Understanding of all parameters
- [ ] Ready to monitor 24/7

---

**🚀 Ready! Copy commands and start!**

_Updated: 2026-02-13_
