# Arbitrage Bot

A cryptocurrency arbitrage bot that monitors multiple exchanges (Bybit, KuCoin, HTX/Huobi, MEXC) for price differences and identifies profitable arbitrage opportunities.

## Features

- Multi-exchange WebSocket connections for real-time price updates
- Order book depth tracking (20 levels)
- Arbitrage opportunity detection with fee calculations
- Paper trading mode (no real orders)
- Automatic reconnection with exponential backoff
- Configurable risk parameters

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/tsepper002/arbitrage-bot.git
cd arbitrage-bot
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Bot

### Paper Mode (Recommended for Testing)

The bot runs in **paper mode** by default, which means it will:
- Connect to exchange WebSocket streams
- Monitor prices and order books
- Detect arbitrage opportunities
- Log all findings
- **NOT execute any real trades**

To run in paper mode:

```bash
export PAPER_MODE=1  # On Windows: set PAPER_MODE=1
python main.py
```

Or run directly (paper mode is default):
```bash
python main.py
```

### Configuration

The bot monitors the following symbols by default:
- BTC-USDT, ETH-USDT, SOL-USDT, BNB-USDT, XRP-USDT
- DOGE-USDT, LTC-USDT, ADA-USDT, MATIC-USDT, DOT-USDT

To modify symbols or other settings, edit `main.py`.

### Exchange Configuration

The bot uses **public WebSocket streams** and does not require API keys for paper mode. For live trading (future feature), you will need:

- Exchange API keys (read and trade permissions)
- Sufficient balance on each exchange
- Proper risk management configuration

**Note:** Live trading features are not included in this release. Do not attempt to place real orders.

## Monitoring

The bot provides several types of output:

1. **Store Monitor**: Shows current price data for each symbol and exchange
2. **Arbitrage Opportunities**: Displays detected profitable trades with ROI calculations
3. **WebSocket Status**: Connection status and reconnection attempts
4. **Price Updates**: Real-time price and order book updates

Example output:
```
[STORE] BTC-USDT: Bybit: bid=89000.0 ask=89010.0 bids_levels=20 asks_levels=20 | KuCoin: bid=89005.0 ask=89015.0 bids_levels=20 asks_levels=20
MARKET BTC-USDT: BEST_BID KuCoin 89005.0 BEST_ASK Bybit 89010.0
ARBITRAGE BTC-USDT: BUY@Bybit 89010.000000 SELL@KuCoin 89005.000000 QTY 0.001000 NET 0.004950 ROI 0.055%
```

## Architecture

### Core Components

- **PriceStore** (`core/price_store.py`): Centralized price and order book storage with async locking
- **ArbitrageEngine** (`core/arbitrage.py`): Scans for arbitrage opportunities across exchanges
- **Exchange Clients** (`exchanges/`): WebSocket clients for each exchange
  - `bybit_ws.py`: Bybit WebSocket client
  - `kucoin_ws.py`: KuCoin WebSocket client
  - `htx_ws.py`: HTX/Huobi WebSocket client
  - `mexc_ws.py`: MEXC WebSocket client

### Data Flow

1. Exchange WS clients connect and subscribe to order book streams
2. Price updates are stored in PriceStore via `update()` or `update_levels()`
3. ArbitrageEngine periodically scans PriceStore for opportunities
4. Opportunities are logged and (in live mode) executed

## Development

### Project Structure

```
arbitrage-bot/
├── core/
│   ├── price_store.py      # Canonical price storage (async)
│   ├── arbitrage.py         # Arbitrage detection engine
│   ├── storage.py           # [LEGACY] Old storage implementation
│   └── store.py             # [LEGACY] Old store implementation
├── exchanges/
│   ├── bybit_ws.py          # Bybit WebSocket client
│   ├── kucoin_ws.py         # KuCoin WebSocket client
│   ├── htx_ws.py            # HTX WebSocket client
│   ├── mexc_ws.py           # MEXC WebSocket client
│   ├── bybit.py             # [LEGACY] Old Bybit implementation
│   └── mexc.py              # [LEGACY] Old MEXC implementation
├── utils/                   # Utility functions
├── main.py                  # Application entry point
└── requirements.txt         # Python dependencies
```

### Extending the Bot

To add a new exchange:

1. Create a new WS client in `exchanges/` following the pattern:
   ```python
   class NewExchangeWS:
       def __init__(self, symbols: List[str], price_store, loop: asyncio.AbstractEventLoop,
                    exchange_name: str = "NewExchange", stagger_start: float = 0.0):
           # Initialize client
           
       def _on_message(self, ws, msg):
           # Parse messages and call:
           # await self.price_store.update_levels(self.exchange, symbol, bids, asks, ts)
           
       def stop(self):
           # Clean shutdown
   ```

2. Add the client to `main.py`:
   ```python
   from .exchanges.newexchange_ws import NewExchangeWS
   
   newex = NewExchangeWS(symbols, store, loop, exchange_name="NewExchange", stagger_start=stagger)
   ```

## Safety & Risk Management

⚠️ **Important Safety Notes**:

- **Always test in paper mode first**
- The bot does NOT place real orders by default
- Real trading requires API keys and explicit configuration
- Cryptocurrency trading involves significant risk
- This software is provided "as is" without warranty

## Roadmap

Future enhancements planned:

1. **Phase 2**: Paper execution module with simulated order fills
2. **Phase 3**: Telegram notifications for opportunities
3. **Phase 4**: Risk manager with exposure limits
4. **Phase 5**: Live trading with real order execution (requires API keys)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

[Add your license here]

## Disclaimer

This software is for educational purposes only. Use at your own risk. The authors are not responsible for any financial losses incurred through the use of this software.

## Support

For issues, questions, or contributions, please open an issue on GitHub.
