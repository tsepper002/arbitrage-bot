# Quick Start Guide - Arbitrage Bot

**Branch**: `copilot/cleanup-stabilization-pass`  
**Repository**: https://github.com/tsepper002/arbitrage-bot

This guide will help you install and run the arbitrage bot on your hardware in under 5 minutes.

---

## 🚀 One-Command Install & Run

### Windows (PowerShell)

```powershell
# Clone, install dependencies, and run
git clone -b copilot/cleanup-stabilization-pass https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Linux / macOS

```bash
# Clone, install dependencies, and run
git clone -b copilot/cleanup-stabilization-pass https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## 📋 Step-by-Step Installation

### Prerequisites

- **Python 3.9+** ([Download](https://www.python.org/downloads/))
- **Git** ([Download](https://git-scm.com/downloads))
- **Internet connection** (for WebSocket feeds)

### 1. Clone the Repository

```bash
git clone -b copilot/cleanup-stabilization-pass https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot
```

### 2. Create Virtual Environment (Recommended)

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

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**
- `aiohttp` - Async HTTP client
- `websockets` - WebSocket protocol
- `websocket-client` - WebSocket client library
- `requests` - HTTP library

### 4. Verify Installation

```bash
python test_core.py
```

You should see:
```
[OK] ALL TESTS PASSED
```

### 5. Run the Bot (Dry Run Mode - Safe)

```bash
python main.py
```

The bot will:
- ✅ Connect to Bybit, KuCoin, and HTX exchanges
- ✅ Monitor real-time order books
- ✅ Detect arbitrage opportunities
- ✅ Log potential trades (NO REAL ORDERS)

---

## ⚙️ Quick Configuration

View current settings:
```bash
python settings.py
```

### Modify Trading Symbols

Edit `settings.py` or set environment variable:

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

### Adjust Performance for Your Hardware

**High-end Hardware (Default):**
```bash
# settings.py already optimized
python main.py
```

**Weak/Laptop Hardware:**

Edit `settings.py`:
```python
SCAN_INTERVAL_SEC = 2.0          # Slower scanning (less CPU)
MONITOR_INTERVAL_SEC = 10.0       # Less log spam
TRADING_SYMBOLS = ["BTC-USDT", "ETH-USDT"]  # Fewer symbols
```

Or use environment variables:
```bash
export ARB_SCAN_INTERVAL_SEC=2.0
export ARB_MONITOR_INTERVAL_SEC=10.0
export ARB_SYMBOLS="BTC-USDT,ETH-USDT"
python main.py
```

---

## 🛠️ Troubleshooting

### Issue: Module not found errors

**Solution:** Ensure virtual environment is activated and dependencies installed
```bash
# Activate venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\Activate.ps1  # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Connection timeout or WebSocket errors

**Solution 1:** Check your internet connection and firewall settings

**Solution 2:** Windows Firewall - Allow Python through firewall
1. Windows Security → Firewall & network protection
2. Allow an app through firewall
3. Find Python, enable Private and Public networks

**Solution 3:** Try with fewer symbols to reduce load
```bash
export ARB_SYMBOLS="BTC-USDT"
python main.py
```

### Issue: High CPU usage

**Solution:** Reduce scan frequency and tracked symbols
```bash
export ARB_SCAN_INTERVAL_SEC=3.0
export ARB_SYMBOLS="BTC-USDT,ETH-USDT"
python main.py
```

### Issue: Unicode/Emoji errors on Windows

**Solution:** This branch includes fixes for Windows Unicode issues. If still seeing errors, ensure you're using Python 3.9+ from Microsoft Store or python.org.

### Issue: "No arbitrage opportunities found"

**This is normal!** Arbitrage opportunities are rare. The bot needs to run continuously to catch them. In dry-run mode, it may take several minutes to hours to detect opportunities depending on market conditions.

---

## 📊 Understanding the Output

### Connection Status
```
[OK] Bybit: Connected
[OK] KuCoin: Connected
[OK] HTX: Connected
```

### Arbitrage Opportunity Detected
```
[DRY RUN] ARBITRAGE OPPORTUNITY DETECTED
   Symbol: BTC-USDT
   Buy:  0.001000 @ $45000.50 on KuCoin (cost: $45.00)
   Sell: 0.001000 @ $45050.75 on Bybit (receive: $45.05)
   Net Profit: $0.0234 (0.052% ROI)
```

### Health Monitoring
```
[OK] Bybit Health: Connected=True, Uptime=120s, Messages=1547, Symbols=10
```

---

## 🔐 Safety Features

✅ **Default Dry Run Mode** - No real trades unless explicitly enabled  
✅ **Rate Limiting** - Max 5 trades per minute  
✅ **Cooldown Periods** - 30s between trades on same symbol  
✅ **Exposure Limits** - Max $200 per trade  
✅ **Safety Factor** - Uses only 50% of available liquidity  

---

## 📚 Next Steps

1. **Read the full README.md** for detailed configuration options
2. **Monitor the bot** for several hours to understand its behavior
3. **Adjust settings** based on your hardware and risk tolerance
4. **Review IMPLEMENTATION_SUMMARY.md** for technical details

---

## ⚠️ Important Notes

- **Dry Run Mode is Default** - The bot will NOT place real orders without configuration
- **Live Trading Requires Setup** - Exchange API keys, authentication, and careful configuration
- **No Financial Advice** - This is educational software. Use at your own risk.
- **Test Thoroughly** - Always run in dry-run mode on new hardware first

---

## 🐛 Getting Help

- **Issues**: https://github.com/tsepper002/arbitrage-bot/issues
- **Full Documentation**: See README.md in this repository
- **Tests**: Run `python test_core.py` to verify installation

---

**Ready to start? Run:**
```bash
python main.py
```

**Happy trading! (safely in dry-run mode)** 🚀
