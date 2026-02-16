# Troubleshooting Guide - Arbitrage Bot

This guide helps resolve common issues when installing and running the arbitrage bot.

---

## ⚠️ IMPORTANT: Version Mismatch Issues

### Problem: Getting Emoji/Unicode Errors or References to Binance

If you see errors like:
```
🔵 DRY RUN
✅ Connected
❌ Disconnected  
Connecting to Binance WebSocket...
UnicodeEncodeError: 'charmap' codec can't encode character...
```

**Root Cause:** You're running an older version of the code that hasn't been updated with the Windows compatibility fixes.

### Solution: Verify You're on the Correct Branch

1. **Check your current branch:**
   ```bash
   git branch
   ```
   
   You should see:
   ```
   * copilot/cleanup-stabilization-pass
   ```

2. **If you're on a different branch, switch:**
   ```bash
   git fetch origin
   git checkout copilot/cleanup-stabilization-pass
   git pull origin copilot/cleanup-stabilization-pass
   ```

3. **Verify the correct version:**
   ```bash
   # Check main.py line count (should be around 136 lines, not 900+)
   wc -l main.py
   
   # Or on Windows:
   python -c "print(len(open('main.py').readlines()))"
   ```
   
   **Expected output:** `136 main.py` (approximately)
   
   **If you see 900+ lines:** You have the wrong version!

4. **Check for emojis (should find none):**
   ```bash
   grep -r "🔵\|✅\|❌" *.py
   ```
   
   **Expected output:** No results (all emojis have been replaced)
   
   **If you see emojis:** Pull the latest changes!

5. **Check for Binance references (should find none):**
   ```bash
   grep -r "Binance" *.py
   ```
   
   **Expected output:** No results
   
   **If you see Binance:** Pull the latest changes!

---

## 🔄 Fresh Installation (Recommended if Issues Persist)

If you're having persistent issues, perform a clean installation:

### Windows (PowerShell)

```powershell
# 1. Remove old installation
cd ..
Remove-Item -Recurse -Force arbitrage-bot

# 2. Fresh clone
git clone -b copilot/cleanup-stabilization-pass https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot

# 3. Create new virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 5. Test
python test_core.py
```

### Linux / macOS

```bash
# 1. Remove old installation
cd ..
rm -rf arbitrage-bot

# 2. Fresh clone
git clone -b copilot/cleanup-stabilization-pass https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot

# 3. Create new virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 5. Test
python test_core.py
```

---

## 🐛 Common Issues

### Issue: "Module not found" errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'websocket'
ModuleNotFoundError: No module named 'aiohttp'
```

**Solution:**

1. Ensure virtual environment is activated:
   ```bash
   # Windows
   .\venv\Scripts\Activate.ps1
   
   # Linux/Mac
   source venv/bin/activate
   ```

2. Reinstall dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Verify installation:
   ```bash
   pip list | grep -E "websocket|aiohttp"
   ```

---

### Issue: WebSocket Connection Errors

**Symptoms:**
```
Connection to remote host was lost
WebSocket error: Connection timeout
```

**Solutions:**

1. **Check internet connection:**
   ```bash
   ping api.bybit.com
   ping api.kucoin.com
   ```

2. **Windows Firewall:**
   - Windows Security → Firewall & network protection
   - Allow an app through firewall
   - Find Python and enable both Private and Public networks

3. **Try with fewer symbols:**
   ```bash
   export ARB_SYMBOLS="BTC-USDT"
   python main.py
   ```

4. **Check if exchanges are accessible:**
   ```bash
   curl https://api.bybit.com/v5/market/time
   curl https://api.kucoin.com/api/v1/timestamp
   ```

---

### Issue: High CPU Usage

**Symptoms:**
- Computer becomes slow
- Fan noise increases
- CPU usage >50%

**Solutions:**

1. **Reduce scan frequency:**
   ```python
   # In settings.py or via environment variable
   export ARB_SCAN_INTERVAL_SEC=3.0
   export ARB_MONITOR_INTERVAL_SEC=10.0
   ```

2. **Track fewer symbols:**
   ```python
   export ARB_SYMBOLS="BTC-USDT,ETH-USDT"
   ```

3. **Close other applications:**
   - Close browser tabs
   - Close unnecessary applications
   - Ensure adequate RAM is available

---

### Issue: "No arbitrage opportunities found"

**This is normal!** 

Arbitrage opportunities are rare and fleeting. The bot needs to:
- Run continuously (hours/days)
- Monitor multiple symbols
- Wait for market conditions

**What to check:**

1. **Verify connections are working:**
   ```
   [OK] Bybit: Connected
   [OK] KuCoin: Connected
   [OK] HTX: Connected
   ```

2. **Check order book updates:**
   ```
   [STORE] Tracking 10 symbols across 30 exchange connections
   ```

3. **Be patient:**
   - In dry-run mode, detection is informational only
   - May take minutes to hours depending on market volatility
   - More symbols = more chances to detect opportunities

---

### Issue: Python Version Errors

**Symptoms:**
```
SyntaxError: invalid syntax
TypeError: unsupported operand type(s)
```

**Solution:**

Ensure you're using Python 3.9 or higher:

```bash
python --version
# or
python3 --version
```

**Expected output:** `Python 3.9.x` or higher

**If version is too old:**
- Windows: Download from python.org or Microsoft Store
- Linux: `sudo apt install python3.9` or `sudo yum install python39`
- macOS: `brew install python@3.9`

---

### Issue: Permission Errors on Windows

**Symptoms:**
```
PermissionError: [WinError 5] Access is denied
```

**Solutions:**

1. **Run PowerShell as Administrator:**
   - Right-click PowerShell
   - Select "Run as Administrator"

2. **Enable script execution:**
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. **Check antivirus:**
   - Some antivirus software blocks Python scripts
   - Add Python and the bot directory to exclusions

---

### Issue: Git Errors

**Symptoms:**
```
fatal: not a git repository
error: pathspec 'copilot/cleanup-stabilization-pass' did not match
```

**Solutions:**

1. **Ensure you're in the right directory:**
   ```bash
   cd /path/to/arbitrage-bot
   pwd  # Check current directory
   ```

2. **Re-clone if needed:**
   ```bash
   cd ..
   rm -rf arbitrage-bot
   git clone -b copilot/cleanup-stabilization-pass https://github.com/tsepper002/arbitrage-bot.git
   cd arbitrage-bot
   ```

---

## 📊 Verifying Installation

Run these commands to verify everything is working:

```bash
# 1. Check branch
git branch
# Expected: * copilot/cleanup-stabilization-pass

# 2. Check main.py size
wc -l main.py
# Expected: Around 136 lines

# 3. Run tests
python test_core.py
# Expected: [OK] ALL TESTS PASSED

# 4. Check configuration
python settings.py
# Expected: Configuration summary without errors

# 5. Test imports
python -c "from exchanges.bybit_ws import BybitWS; print('Imports OK')"
# Expected: Imports OK (may show websocket warning, that's fine)
```

---

## 🔍 Debug Mode

To get more detailed information about what's happening:

```bash
# Enable DEBUG logging
export ARB_LOG_LEVEL=DEBUG
python main.py
```

This will show:
- Detailed WebSocket messages
- Order book updates
- Connection attempts
- Parsing details

**Warning:** DEBUG mode generates a LOT of output. Use only for troubleshooting.

---

## 📝 Reporting Issues

If you're still having problems, gather this information:

1. **System info:**
   ```bash
   python --version
   pip --version
   # On Windows: $PSVersionTable.PSVersion
   # On Linux/Mac: uname -a
   ```

2. **Current branch:**
   ```bash
   git branch
   git log --oneline -3
   ```

3. **Installed packages:**
   ```bash
   pip list
   ```

4. **Error message:**
   - Copy the complete error message
   - Include the traceback
   - Note what command you ran

5. **Configuration:**
   ```bash
   python settings.py
   ```

---

## 💡 Best Practices

1. **Always use a virtual environment**
   - Isolates dependencies
   - Prevents conflicts
   - Easy to reset

2. **Keep your installation up to date**
   ```bash
   git pull origin copilot/cleanup-stabilization-pass
   pip install --upgrade -r requirements.txt
   ```

3. **Start with default settings**
   - Don't modify settings.py initially
   - Use environment variables for changes
   - Test with one symbol first

4. **Monitor resource usage**
   - Task Manager (Windows)
   - htop/top (Linux)
   - Activity Monitor (macOS)

5. **Run in dry-run mode first**
   - Always test on new hardware
   - Verify connections work
   - Understand bot behavior

---

## 🆘 Getting Help

- **Documentation**: See README.md and QUICKSTART.md
- **Issues**: https://github.com/tsepper002/arbitrage-bot/issues
- **Tests**: Run `python test_core.py` to verify core functionality

---

**Last Updated:** 2026-02-16  
**For Branch:** copilot/cleanup-stabilization-pass
