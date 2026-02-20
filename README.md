# Cryptocurrency Arbitrage Bot

A robust, efficient arbitrage bot for detecting and executing cross-exchange arbitrage opportunities across Bybit, KuCoin, and HTX (Huobi).

## Features

- **Real-time Order Book Monitoring**: WebSocket connections to multiple exchanges with automatic reconnection
- **Arbitrage Detection**: Intelligent scanning for profitable cross-exchange opportunities
- **Dual Execution Modes**: Safe dry-run simulation and live trading capability
- **Risk Management**: Configurable limits on exposure, trade frequency, and position sizes
- **Performance Optimized**: Event-driven scanning optimized for weak hardware (including Windows 11 laptops)
- **Health Monitoring**: Automatic detection of stale streams and connection issues

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Running on Windows 11](#running-on-windows-11)
- [Dry Run vs Live Mode](#dry-run-vs-live-mode)
- [Performance Tuning](#performance-tuning)
- [Risk Management](#risk-management)
- [Troubleshooting](#troubleshooting)

## Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager
- Internet connection for exchange WebSocket feeds

### Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `aiohttp` - Async HTTP client for REST API calls
- `websockets` - WebSocket protocol support
- `websocket-client` - Additional WebSocket client library

## Quick Start

### One-liner: pull & run (Windows)

```cmd
cd C:\path\to\arbitrage-bot && git pull && pip install -r requirements.txt && python main.py --mode dry-run
```

Or simply double-click **`start.bat`** (included in the repo).

```cmd
start.bat              &REM dry-run (default)
start.bat live         &REM live trading
```

### 1. Basic Usage (Dry Run Mode - Safe)

By default, the bot runs in **dry-run mode**, which simulates all trades without placing real orders:

```bash
python main.py --mode dry-run
```

Other CLI options:

```bash
python main.py --mode live                          # live trading (requires setup)
python main.py --symbols BTC-USDT,ETH-USDT          # override trading pairs
python main.py --log-level DEBUG                     # verbose logging
python main.py --mode dry-run --symbols BTC-USDT     # combine options
```

This will:
- Connect to Bybit, KuCoin, and HTX WebSocket feeds
- Monitor real-time order books for configured symbols
- Detect arbitrage opportunities
- Log intended trades (but not execute them)
- Display statistics

### 2. View Current Configuration

```bash
python settings.py
```

This displays all current settings and checks for configuration issues.

### 3. Monitor Output

The bot will display:
- Connection status for each exchange
- Detected arbitrage opportunities with expected profit
- Periodic statistics (total opportunities, profit if executed, etc.)

Example output:
```
💰 [DRY RUN] ARBITRAGE OPPORTUNITY DETECTED
   Symbol: BTC-USDT
   Buy:  0.001000 @ $45000.50 on KuCoin (cost: $45.00)
   Sell: 0.001000 @ $45050.75 on Bybit (receive: $45.05)
   Net Profit: $0.0234 (0.052% ROI)
```

## Configuration

All configuration is managed in `settings.py`. You can modify defaults directly in the file or override via environment variables.

### Key Configuration Parameters

#### Execution Mode

| Parameter | Default | Environment Variable | Description |
|-----------|---------|---------------------|-------------|
| `DRY_RUN` | `True` | `ARB_DRY_RUN` | If True, simulates orders. If False, places real orders (requires setup) |

#### Risk Management

| Parameter | Default | Environment Variable | Description |
|-----------|---------|---------------------|-------------|
| `MIN_NET_ROI_PCT` | `0.05` | `ARB_MIN_NET_ROI_PCT` | Minimum net ROI % required (after fees) |
| `MAX_EXPOSURE_USDT` | `200.0` | `ARB_MAX_EXPOSURE_USDT` | Maximum $ exposure per trade |
| `SAFETY_FACTOR` | `0.5` | `ARB_SAFETY_FACTOR` | Use max 50% of available liquidity |
| `MAX_TRADES_PER_MINUTE` | `5` | `ARB_MAX_TRADES_PER_MINUTE` | Rate limit: max trades per minute |
| `PER_SYMBOL_COOLDOWN_SEC` | `30.0` | `ARB_SYMBOL_COOLDOWN_SEC` | Cooldown before trading same symbol again |
| `MAX_CONCURRENT_OPPORTUNITIES` | `3` | `ARB_MAX_CONCURRENT_OPPS` | Max opportunities to process per cycle |

#### Performance & Throttling

| Parameter | Default | Environment Variable | Description |
|-----------|---------|---------------------|-------------|
| `SCAN_INTERVAL_SEC` | `1.0` | `ARB_SCAN_INTERVAL_SEC` | Time between scan cycles |
| `MONITOR_INTERVAL_SEC` | `5.0` | `ARB_MONITOR_INTERVAL_SEC` | Reduce log spam |
| `EVENT_DRIVEN_SCAN` | `True` | `ARB_EVENT_DRIVEN_SCAN` | Only scan when order books update |
| `MIN_SCAN_INTERVAL_PER_SYMBOL_SEC` | `0.5` | `ARB_MIN_SCAN_INTERVAL_PER_SYMBOL` | Throttle per-symbol scanning |

#### WebSocket Reliability

| Parameter | Default | Environment Variable | Description |
|-----------|---------|---------------------|-------------|
| `WS_AUTO_RECONNECT` | `True` | `ARB_WS_AUTO_RECONNECT` | Automatically reconnect on disconnect |
| `WS_RECONNECT_DELAY_SEC` | `5.0` | `ARB_WS_RECONNECT_DELAY` | Initial reconnect delay |
| `WS_MAX_RECONNECT_DELAY_SEC` | `300.0` | `ARB_WS_MAX_RECONNECT_DELAY` | Max delay (exponential backoff cap) |
| `STREAM_STALENESS_THRESHOLD_SEC` | `60.0` | `ARB_STREAM_STALENESS_SEC` | Alert if no updates for this duration |
| `HEALTH_CHECK_INTERVAL_SEC` | `30.0` | `ARB_HEALTH_CHECK_INTERVAL` | How often to check connection health |

### Using Environment Variables

Set environment variables to override defaults without modifying code:

**Linux/Mac:**
```bash
export ARB_DRY_RUN=True
export ARB_MIN_NET_ROI_PCT=0.1
export ARB_MAX_EXPOSURE_USDT=100
python -m main
```

**Windows (PowerShell):**
```powershell
$env:ARB_DRY_RUN="True"
$env:ARB_MIN_NET_ROI_PCT="0.1"
$env:ARB_MAX_EXPOSURE_USDT="100"
python -m main
```

**Windows (Command Prompt):**
```cmd
set ARB_DRY_RUN=True
set ARB_MIN_NET_ROI_PCT=0.1
set ARB_MAX_EXPOSURE_USDT=100
python -m main
```

## Running on Windows 11

The bot is optimized for Windows 11, including support for weak hardware (e.g., laptops with limited CPU/RAM).

### Windows-Specific Setup

1. **Install Python from Microsoft Store** (recommended) or python.org
   ```powershell
   # Verify installation
   python --version
   ```

2. **Install Git for Windows** (if cloning repository)
   - Download from https://git-scm.com/download/win

3. **Install dependencies in a virtual environment** (recommended)
   ```powershell
   # Create virtual environment
   python -m venv venv
   
   # Activate it
   .\venv\Scripts\Activate.ps1
   
   # Install dependencies
   pip install -r requirements.txt
   ```

### Performance Tips for Windows 11

#### For Weak/Laptop Hardware:

1. **Reduce CPU usage** by adjusting scan frequency:
   ```python
   # In settings.py or via environment variables
   SCAN_INTERVAL_SEC = 2.0  # Increase from default 1.0
   MIN_SCAN_INTERVAL_PER_SYMBOL_SEC = 1.0  # Increase from 0.5
   ```

2. **Reduce log spam** to minimize I/O:
   ```python
   MONITOR_INTERVAL_SEC = 10.0  # Increase from 5.0
   LOG_LEVEL = "INFO"  # Change from "DEBUG"
   ```

3. **Enable event-driven scanning** (already default):
   ```python
   EVENT_DRIVEN_SCAN = True  # Only scans when order books change
   ```

4. **Reduce tracked symbols** if needed:
   ```python
   # In settings.py
   TRADING_SYMBOLS = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]  # Fewer symbols = less CPU
   ```

5. **Run with reduced priority** (optional):
   ```powershell
   Start-Process python -ArgumentList "-m","main" -NoNewWindow -Priority BelowNormal
   ```

### Windows Firewall

If you encounter connection issues, ensure Python is allowed through Windows Firewall:
1. Open Windows Security → Firewall & network protection
2. Allow an app through firewall
3. Find Python and ensure both Private and Public networks are checked

## Dry Run vs Live Mode

### Dry Run Mode (Default - Safe)

**When to use:**
- Testing and development
- Learning how the bot works
- Backtesting strategies
- Initial deployment on new hardware
- ANY TIME you're not ready for real trading

**What it does:**
- ✅ Monitors real-time order books
- ✅ Detects real arbitrage opportunities
- ✅ Logs detailed execution plans
- ✅ Tracks statistics
- ❌ Does NOT place real orders
- ❌ Does NOT use real money

**Enable (default):**
```python
# settings.py
DRY_RUN = True
```

### Live Mode (Real Trading)

**⚠️ WARNING: Only use when you understand the risks and have properly configured exchange API credentials!**

**Prerequisites for live mode:**
1. Funded accounts on Bybit, KuCoin, and/or HTX
2. API keys with trading permissions
3. Properly configured exchange REST clients
4. Thorough testing in dry-run mode
5. Understanding of trading risks

**To enable live mode:**
1. Implement authenticated exchange clients in `core/order_executor.py`
2. Set up API credentials (see exchange documentation)
3. Test thoroughly with small amounts first
4. Enable live mode:
   ```python
   # settings.py
   DRY_RUN = False
   ```

**Current Status:**
Live order placement is **not fully implemented**. The `_execute_live()` method in `core/order_executor.py` contains a template and placeholder. You must:
- Add authenticated API client integration
- Implement order placement logic
- Add balance checking
- Implement order fill verification
- Add error handling and rollback logic

## Performance Tuning

### Optimize for Speed (Strong Hardware)

```python
# settings.py
SCAN_INTERVAL_SEC = 0.5  # Faster scanning
MIN_SCAN_INTERVAL_PER_SYMBOL_SEC = 0.2
EVENT_DRIVEN_SCAN = True  # Still recommended
MONITOR_INTERVAL_SEC = 2.0  # More frequent monitoring
```

### Optimize for Efficiency (Weak Hardware)

```python
# settings.py
SCAN_INTERVAL_SEC = 2.0  # Slower scanning
MIN_SCAN_INTERVAL_PER_SYMBOL_SEC = 1.0
EVENT_DRIVEN_SCAN = True  # Critical for efficiency
MONITOR_INTERVAL_SEC = 10.0  # Reduce output
LOG_LEVEL = "INFO"  # Less verbose logging
```

### Optimize for Conservative Trading

```python
# settings.py
MIN_NET_ROI_PCT = 0.1  # Higher profit threshold
MAX_EXPOSURE_USDT = 100.0  # Lower exposure
SAFETY_FACTOR = 0.3  # Use less of available liquidity
MAX_TRADES_PER_MINUTE = 2  # Fewer trades
PER_SYMBOL_COOLDOWN_SEC = 60.0  # Longer cooldown
```

## Risk Management

The bot includes multiple layers of risk management:

### 1. Minimum ROI Threshold
Only opportunities with net profit (after fees) above `MIN_NET_ROI_PCT` are considered.

### 2. Exposure Limits
Each trade is capped at `MAX_EXPOSURE_USDT` to limit position size.

### 3. Liquidity Safety Factor
Only `SAFETY_FACTOR` (default 50%) of available order book liquidity is used to avoid slippage.

### 4. Rate Limiting
- Max `MAX_TRADES_PER_MINUTE` trades per minute
- Per-symbol cooldown of `PER_SYMBOL_COOLDOWN_SEC` seconds

### 5. Concurrent Opportunity Limit
Maximum of `MAX_CONCURRENT_OPPORTUNITIES` opportunities processed per scan cycle.

### 6. Fee Calculations
All profit calculations include:
- Maker fees (if applicable)
- Taker fees
- Slippage estimates based on order book depth

### Recommended Conservative Settings

```python
MIN_NET_ROI_PCT = 0.1  # At least 0.1% profit after fees
MAX_EXPOSURE_USDT = 200.0  # Max $200 per trade
SAFETY_FACTOR = 0.5  # Use max 50% of liquidity
MAX_TRADES_PER_MINUTE = 5  # Max 5 trades/minute
PER_SYMBOL_COOLDOWN_SEC = 30.0  # 30s between same-symbol trades
```

## Troubleshooting

### Connection Issues

**Problem:** WebSocket connections fail or disconnect frequently

**Solutions:**
1. Check internet connection stability
2. Verify firewall settings (see Windows Firewall section)
3. Increase reconnection delay:
   ```python
   WS_RECONNECT_DELAY_SEC = 10.0
   ```
4. Check exchange status pages for outages

### High CPU Usage

**Problem:** Bot uses too much CPU on weak hardware

**Solutions:**
1. Increase scan interval:
   ```python
   SCAN_INTERVAL_SEC = 2.0  # or higher
   ```
2. Reduce number of symbols:
   ```python
   TRADING_SYMBOLS = ["BTC-USDT", "ETH-USDT"]  # Fewer symbols
   ```
3. Ensure event-driven scanning is enabled:
   ```python
   EVENT_DRIVEN_SCAN = True
   ```
4. Reduce logging verbosity:
   ```python
   LOG_LEVEL = "WARNING"  # or "ERROR"
   ```

### No Opportunities Found

**Problem:** Bot runs but finds no arbitrage opportunities

**Possible causes:**
1. **Markets are efficient** - This is normal. Arbitrage opportunities are rare.
2. **ROI threshold too high** - Lower `MIN_NET_ROI_PCT`
3. **Exposure limit too low** - Increase `MAX_EXPOSURE_USDT`
4. **Order book data not loading** - Check logs for connection issues

**Not a problem if:**
- You see "Tracking X symbols across Y exchange connections" in logs
- WebSocket connections are healthy
- Markets are simply efficient (expected)

### Stale Stream Warnings

**Problem:** Logs show "Stream for X is stale"

**Solutions:**
1. This indicates no order book updates for a symbol
2. Check if exchange is experiencing issues
3. Verify symbol is actively traded
4. Adjust staleness threshold if needed:
   ```python
   STREAM_STALENESS_THRESHOLD_SEC = 120.0  # Increase from 60s
   ```

### Module Import Errors

**Problem:** `ModuleNotFoundError` or import errors

**Solutions:**
1. Ensure you're running from the correct directory:
   ```bash
   # Must be in arbitrage-bot directory
   python -m main
   ```
2. Verify virtual environment is activated
3. Reinstall dependencies:
   ```bash
   pip install --force-reinstall -r requirements.txt
   ```

## Project Structure

```
arbitrage-bot/
├── main.py                      # Entry point
├── settings.py                  # Configuration (NEW)
├── requirements.txt             # Dependencies
├── config.py                    # Legacy exchange parameters
├── core/                        # Core logic
│   ├── arbitrage.py            # Main engine (ENHANCED)
│   ├── order_executor.py       # Order execution layer (NEW)
│   ├── price_store.py          # Order book storage
│   ├── scanner.py              # Opportunity detection
│   ├── calculator.py           # Profit calculations
│   ├── exchange_config.py      # Fee configurations
│   └── trader_config.py        # Trader settings
├── exchanges/                   # Exchange clients
│   ├── base_ws.py              # Base WebSocket class (NEW)
│   ├── bybit_ws.py             # Bybit WebSocket
│   ├── kucoin_ws.py            # KuCoin WebSocket
│   ├── htx_ws.py               # HTX WebSocket
│   └── *.py                    # Other exchange files
└── utils/                       # Utilities
    ├── logger.py
    ├── throttle.py
    └── helpers.py
```

## Exchange Fee Information

Current fee rates configured in `core/exchange_config.py`:

| Exchange | Maker Fee | Taker Fee |
|----------|-----------|-----------|
| Bybit    | 0.02%     | 0.06%     |
| KuCoin   | 0.01%     | 0.06%     |
| HTX      | 0.00%     | 0.20%     |

**Note:** Fees may vary based on account tier and trading volume. Update `core/exchange_config.py` if you have different fee rates.

## Support & Contributing

This bot is designed for educational and research purposes. Trading cryptocurrency carries significant risk.

**Before using with real funds:**
1. Thoroughly test in dry-run mode
2. Understand all risks involved
3. Start with minimal capital
4. Monitor actively during initial runs
5. Ensure you have proper risk management

## License

See LICENSE file for details.

## Disclaimer

**IMPORTANT:** This software is provided for educational purposes only. Cryptocurrency trading involves substantial risk of loss. The authors are not responsible for any financial losses incurred through use of this software. Always do your own research and never trade with money you cannot afford to lose.

Use at your own risk. No warranty is provided.
