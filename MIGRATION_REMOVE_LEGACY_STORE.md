# Migration Guide: Removal of Legacy Storage Modules

## Overview
This document describes the removal of legacy storage implementations (`core/storage.py` and `core/store.py`) from the arbitrage-bot repository as part of code consolidation efforts.

**Date**: 2026-02-01  
**PR**: WIP: Remove legacy storage modules (core/storage.py, core/store.py)  
**Status**: Work In Progress

## What Was Removed

### 1. `core/storage.py`
A synchronous storage implementation using threading locks:
- **Class**: `PriceStorage`
- **Key methods**: `update(exchange, pair, bid, ask)`, `get(exchange, pair)`
- **Architecture**: Thread-based synchronization with `threading.Lock()`

<details>
<summary>Original core/storage.py content</summary>

```python
import time
import threading


class PriceStorage:
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()

    def update(self, exchange, pair, bid, ask):
        with self.lock:
            self.data.setdefault(exchange, {})
            self.data[exchange][pair] = {
                "bid": bid,
                "ask": ask,
                "ts": time.time()
            }

    def get(self, exchange, pair):
        return self.data.get(exchange, {}).get(pair)
```

</details>

### 2. `core/store.py`
An async storage implementation with simplified API:
- **Class**: `PriceStore`
- **Key methods**: `async update(exchange, symbol, price)`, `async get(symbol)`
- **Architecture**: Async-based with `asyncio.Lock()`

<details>
<summary>Original core/store.py content</summary>

```python
import asyncio
from collections import defaultdict


class PriceStore:
    def __init__(self):
        self.data = defaultdict(dict)
        self.lock = asyncio.Lock()

    async def update(self, exchange, symbol, price):
        async with self.lock:
            self.data[symbol][exchange] = price

    async def get(self, symbol):
        async with self.lock:
            return dict(self.data[symbol])
```

</details>

## Current Implementation

The repository now uses **only** `core/price_store.py`, which provides:
- **Class**: `PriceStore`
- **Full orderbook support**: Stores bid/ask prices, sizes, and multi-level orderbook data
- **Methods**:
  - `async update(exchange, symbol, bid, bid_size, ask, ask_size, ts)` - Update top-of-book
  - `async update_levels(exchange, symbol, bids_levels, asks_levels, ts)` - Update full orderbook levels
  - `async get(symbol)` - Retrieve all exchange data for a symbol
  - `snapshot()` - Get complete store snapshot (non-async)
- **Architecture**: Async-based with comprehensive logging and type hints

## Why This Change Was Necessary

1. **Multiple conflicting APIs**: The codebase had three different storage implementations with incompatible interfaces
2. **Async/await confusion**: Mixing sync (`storage.py`) and async (`store.py`, `price_store.py`) patterns caused runtime errors
3. **Feature gaps**: Legacy implementations lacked orderbook depth support needed for WebSocket integrations
4. **Maintenance burden**: Maintaining three implementations increased complexity and risk of bugs

## Migration Instructions

### If Your Code Used `core.storage.PriceStorage`

**Before**:
```python
from core.storage import PriceStorage

storage = PriceStorage()
storage.update("Binance", "BTC-USDT", bid=50000.0, ask=50001.0)
data = storage.get("Binance", "BTC-USDT")
```

**After**:
```python
from core.price_store import PriceStore

store = PriceStore()
await store.update("Binance", "BTC-USDT", 
                   bid=50000.0, bid_size=1.0,
                   ask=50001.0, ask_size=1.0)
all_exchanges = await store.get("BTC-USDT")
data = all_exchanges.get("Binance", {})
```

### If Your Code Used `core.store.PriceStore`

**Before**:
```python
from core.store import PriceStore

store = PriceStore()
await store.update("Binance", "BTC-USDT", price=50000.0)
prices = await store.get("BTC-USDT")
```

**After**:
```python
from core.price_store import PriceStore

store = PriceStore()
# Note: price_store requires bid/ask separately
await store.update("Binance", "BTC-USDT",
                   bid=50000.0, bid_size=1.0,
                   ask=50000.0, ask_size=1.0)
prices = await store.get("BTC-USDT")
```

## Current Usage

As of this PR, the codebase uses `core.price_store.PriceStore` in:
- `main.py` - Main entry point, instantiates PriceStore and passes to exchanges
- `core/arbitrage.py` - ArbitrageEngine reads from store via `snapshot()` method
- All WebSocket exchange clients (`exchanges/*_ws.py`) - Update store via `update_levels()`

## How to Recover Legacy Files

If you need to restore the removed files for reference:

### Option 1: View in Git History
```bash
# View core/storage.py from the commit before deletion
git show HEAD~1:core/storage.py

# View core/store.py from the commit before deletion
git show HEAD~1:core/store.py
```

### Option 2: Checkout from Previous Commit
```bash
# Create a temporary branch at the commit before removal
git checkout <commit-hash-before-deletion> -b temp-legacy-storage

# Copy the files you need
cp core/storage.py /path/to/backup/
cp core/store.py /path/to/backup/

# Return to main branch
git checkout main
git branch -d temp-legacy-storage
```

### Option 3: View in GitHub PR
The full diff showing removed content is available in the PR for this change.

## Testing Performed

1. ✅ Import verification: `python -c "import core.price_store"`
2. ✅ Main module import: `python -c "import main"`
3. ✅ No broken imports detected in codebase
4. ✅ Codebase scan confirmed no usage of legacy modules

## Impact Assessment

- **Breaking changes**: None - legacy modules were not in use
- **Required code updates**: None - all code already uses `core.price_store`
- **Risk level**: Low - files were not referenced anywhere in the codebase

## Questions or Issues?

If you encounter problems after this change:
1. Check your imports are using `from core.price_store import PriceStore`
2. Ensure your code uses async/await for store operations
3. Review the migration examples above
4. Check the PR discussion for additional context

## Related PRs
- None yet

---
*This migration guide was created as part of PR: "WIP: Remove legacy storage modules (core/storage.py, core/store.py)"*
