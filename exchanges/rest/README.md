# REST API Clients

Production-ready authenticated REST API clients for cryptocurrency exchanges.

## Overview

This module provides REST API clients for the following exchanges:
- **Bybit** - V5 Unified Trading API
- **KuCoin** - Spot Trading API
- **HTX** (Huobi) - Spot Trading API
- **XT.COM** - Spot Trading API
- **MEXC** - Spot Trading API v3

All clients inherit from `BaseRestClient` and implement standardized methods for:
- Getting account balances
- Placing orders (market and limit)
- Canceling orders
- Querying order status

## Installation

No additional dependencies required beyond the base requirements:
```bash
pip install requests
```

## Configuration

Set environment variables for API credentials:

```bash
# Bybit
export BYBIT_API_KEY="your_api_key"
export BYBIT_API_SECRET="your_api_secret"

# KuCoin (requires passphrase)
export KUCOIN_API_KEY="your_api_key"
export KUCOIN_API_SECRET="your_api_secret"
export KUCOIN_API_PASSPHRASE="your_passphrase"

# HTX (Huobi)
export HTX_API_KEY="your_api_key"
export HTX_API_SECRET="your_api_secret"

# XT.COM
export XT_API_KEY="your_api_key"
export XT_API_SECRET="your_api_secret"

# MEXC
export MEXC_API_KEY="your_api_key"
export MEXC_API_SECRET="your_api_secret"
```

## Usage

### Basic Example

```python
from exchanges.rest import BybitRestClient

# Initialize client (uses environment variables)
client = BybitRestClient()

# Or with explicit credentials
client = BybitRestClient(
    api_key='your_key',
    api_secret='your_secret'
)

# Get balance
balances = client.get_balance()
print(f"All balances: {balances}")

# Get specific currency
usdt = client.get_balance(currency='USDT')
print(f"USDT balance: {usdt}")

# Place limit order
order = client.place_order(
    symbol='BTC-USDT',
    side='buy',
    order_type='limit',
    quantity=0.001,
    price=40000.0
)
print(f"Order ID: {order['order_id']}")

# Check order status
status = client.get_order_status(
    order_id=order['order_id'],
    symbol='BTC-USDT'
)
print(f"Status: {status['status']}")

# Cancel order
cancel = client.cancel_order(
    order_id=order['order_id'],
    symbol='BTC-USDT'
)
print(f"Cancelled: {cancel}")
```

### Exchange-Specific Examples

#### Bybit
```python
from exchanges.rest import BybitRestClient

client = BybitRestClient()
balances = client.get_balance()

# Symbol format: BTCUSDT (no separator)
order = client.place_order(
    symbol='BTC-USDT',  # Automatically normalized
    side='buy',
    order_type='limit',
    quantity=0.001,
    price=40000.0
)
```

#### KuCoin
```python
from exchanges.rest import KuCoinRestClient

# KuCoin requires passphrase
client = KuCoinRestClient()
balances = client.get_balance()

# Symbol format: BTC-USDT (with hyphen)
order = client.place_order(
    symbol='BTC-USDT',
    side='buy',
    order_type='limit',
    quantity=0.001,
    price=40000.0
)
```

#### HTX (Huobi)
```python
from exchanges.rest import HTXRestClient

client = HTXRestClient()
balances = client.get_balance()

# Symbol format: btcusdt (lowercase, no separator)
order = client.place_order(
    symbol='BTC-USDT',  # Automatically normalized
    side='buy',
    order_type='limit',
    quantity=0.001,
    price=40000.0
)
```

#### XT.COM
```python
from exchanges.rest import XTRestClient

client = XTRestClient()
balances = client.get_balance()

# Symbol format: btc_usdt (lowercase with underscore)
order = client.place_order(
    symbol='BTC-USDT',  # Automatically normalized
    side='BUY',
    order_type='LIMIT',
    quantity=0.001,
    price=40000.0
)
```

#### MEXC
```python
from exchanges.rest import MEXCRestClient

client = MEXCRestClient()
balances = client.get_balance()

# Symbol format: BTCUSDT (uppercase, no separator)
order = client.place_order(
    symbol='BTC-USDT',  # Automatically normalized
    side='BUY',
    order_type='LIMIT',
    quantity=0.001,
    price=40000.0
)
```

## Symbol Formats

Each exchange has different symbol format requirements. The clients automatically normalize symbols:

| Exchange | Format | Example | Input Examples |
|----------|--------|---------|----------------|
| Bybit | BTCUSDT | BTCUSDT | BTC-USDT, btc_usdt |
| KuCoin | BTC-USDT | BTC-USDT | BTCUSDT, btc_usdt |
| HTX | btcusdt | btcusdt | BTC-USDT, BTCUSDT |
| XT.COM | btc_usdt | btc_usdt | BTC-USDT, BTCUSDT |
| MEXC | BTCUSDT | BTCUSDT | BTC-USDT, btc_usdt |

You can use any common format (BTC-USDT, BTC_USDT, BTCUSDT) and it will be normalized automatically.

## API Methods

All clients implement these methods:

### `get_balance(currency: Optional[str] = None) -> Dict[str, float]`
Get account balance(s).
```python
# Get all balances
all_balances = client.get_balance()
# {'BTC': 0.5, 'USDT': 10000.0, 'ETH': 2.0}

# Get specific currency
usdt_balance = client.get_balance(currency='USDT')
# {'USDT': 10000.0}
```

### `place_order(symbol, side, order_type, quantity, price=None, time_in_force='GTC')`
Place a new order.
```python
# Limit order
order = client.place_order(
    symbol='BTC-USDT',
    side='buy',
    order_type='limit',
    quantity=0.001,
    price=40000.0,
    time_in_force='GTC'
)

# Market order
order = client.place_order(
    symbol='BTC-USDT',
    side='sell',
    order_type='market',
    quantity=0.001
)
```

### `cancel_order(order_id: str, symbol: str) -> Dict[str, Any]`
Cancel an open order.
```python
result = client.cancel_order(
    order_id='123456789',
    symbol='BTC-USDT'
)
```

### `get_order_status(order_id: str, symbol: str) -> Dict[str, Any]`
Query order details and status.
```python
status = client.get_order_status(
    order_id='123456789',
    symbol='BTC-USDT'
)
# Returns: order_id, status, executed_qty, avg_price, etc.
```

## Authentication

Each exchange uses HMAC SHA256 authentication with different signature formats:

- **Bybit**: `timestamp + api_key + recv_window + query_string`
- **KuCoin**: `timestamp + method + endpoint + body` (also signs passphrase)
- **HTX**: Canonical request format with sorted parameters
- **XT.COM**: `timestamp + "#" + method + "#" + endpoint + "#" + params`
- **MEXC**: Binance-style with signature in query parameters

All authentication is handled automatically by the clients.

## Error Handling

All methods include comprehensive error handling:

```python
try:
    order = client.place_order(
        symbol='BTC-USDT',
        side='buy',
        order_type='limit',
        quantity=0.001,
        price=40000.0
    )
    print(f"Order placed: {order['order_id']}")
except ValueError as e:
    print(f"Invalid parameters: {e}")
except Exception as e:
    print(f"Order failed: {e}")
```

Errors are logged with the `logging` module. Configure logging as needed:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('rest_client')
```

## Testing

Run the included examples and tests:

```bash
# Run symbol normalization tests
python3 -m exchanges.rest.examples

# Test with real credentials (set env vars first)
export BYBIT_API_KEY="your_key"
export BYBIT_API_SECRET="your_secret"
python3 -m exchanges.rest.examples
```

## Security Best Practices

1. **Never hardcode API credentials** - Use environment variables
2. **Use API key restrictions** - Limit IP addresses and permissions on exchange
3. **Enable withdrawal whitelist** - On exchanges that support it
4. **Monitor API usage** - Set up alerts for unusual activity
5. **Rotate keys regularly** - Change API keys periodically
6. **Use read-only keys for testing** - When possible, test with restricted keys

## Rate Limits

Each exchange has different rate limits. The clients do not currently implement rate limiting. Consider adding:

```python
import time
from functools import wraps

def rate_limit(calls_per_second=10):
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator
```

## Architecture

```
exchanges/rest/
├── __init__.py           # Module exports
├── base_rest.py          # Base client with common functionality
├── bybit_rest.py         # Bybit implementation
├── kucoin_rest.py        # KuCoin implementation
├── htx_rest.py           # HTX implementation
├── xt_rest.py            # XT.COM implementation
├── mexc_rest.py          # MEXC implementation
├── examples.py           # Usage examples and tests
└── README.md             # This file
```

## Contributing

When adding a new exchange:

1. Create a new file `{exchange}_rest.py`
2. Inherit from `BaseRestClient`
3. Implement required methods:
   - `_get_base_url()`
   - `_sign_request()`
   - `get_balance()`
   - `place_order()`
   - `cancel_order()`
   - `get_order_status()`
4. Add symbol normalization helper `_normalize_symbol()`
5. Update `__init__.py` with new export
6. Add examples to `examples.py`
7. Document in this README

## License

Part of the Arbitrage Bot project.
