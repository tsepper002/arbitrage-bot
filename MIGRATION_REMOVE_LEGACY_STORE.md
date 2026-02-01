# Migration: Removal of Legacy Storage Modules

## Overview
This document describes the removal of legacy storage implementations (`core/storage.py` and `core/store.py`) from the arbitrage-bot repository. These modules have been deprecated in favor of the unified implementation in `core/price_store.py`.

## What Was Removed

### 1. core/storage.py
Legacy synchronous storage implementation with thread-based locking.

**Removed on:** 2026-02-01  
**Reason:** Replaced by async implementation in `core/price_store.py`

<details>
<summary>Click to view original code</summary>

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

### 2. core/store.py
Legacy async storage implementation with simplified API.

**Removed on:** 2026-02-01  
**Reason:** Replaced by enhanced async implementation in `core/price_store.py`

<details>
<summary>Click to view original code</summary>

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

## Why This Change Was Made

### Problems with Multiple Storage Implementations
1. **API Inconsistency:** Three different implementations with different APIs caused confusion
2. **Async/Await Errors:** Mixing sync and async storage patterns led to runtime errors
3. **Limited Features:** Legacy implementations lacked order book depth support (bids_levels, asks_levels)
4. **Maintenance Burden:** Multiple implementations increased code complexity and testing overhead

### Benefits of Consolidation
- ✅ Single source of truth: `core/price_store.py`
- ✅ Consistent async API across all exchange clients
- ✅ Full order book support with bid/ask levels
- ✅ Better type hints and logging
- ✅ Reduced potential for regression

## Migration Guide

### Current Implementation: core/price_store.py

The unified `PriceStore` class provides:

```python
from core.price_store import PriceStore

store = PriceStore()

# Update top-of-book (bid/ask with sizes)
await store.update(
    exchange="BYBIT",
    symbol="BTC-USDT",
    bid=50000.0,
    bid_size=1.5,
    ask=50001.0,
    ask_size=2.0,
    ts=None  # optional, defaults to current time
)

# Update with order book levels
await store.update_levels(
    exchange="BYBIT",
    symbol="BTC-USDT",
    bids_levels=[(50000.0, 1.5), (49999.0, 2.0), ...],
    asks_levels=[(50001.0, 2.0), (50002.0, 1.8), ...],
    ts=None
)

# Get data for a symbol (async)
data = await store.get("BTC-USDT")
# Returns: {"BYBIT": {"bid": 50000.0, "ask": 50001.0, ...}, ...}

# Get full snapshot (sync, for monitoring)
snapshot = store.snapshot()
# Returns: {"BTC-USDT": {"BYBIT": {...}, "KUCOIN": {...}}, ...}
```

### For Code That Used core.storage.PriceStorage

**Old code:**
```python
from core.storage import PriceStorage

storage = PriceStorage()
storage.update("BYBIT", "BTC-USDT", 50000.0, 50001.0)
data = storage.get("BYBIT", "BTC-USDT")
```

**New code:**
```python
from core.price_store import PriceStore

store = PriceStore()
await store.update("BYBIT", "BTC-USDT", 50000.0, None, 50001.0, None)
# To get data for specific exchange/symbol, use snapshot:
snapshot = store.snapshot()
data = snapshot.get("BTC-USDT", {}).get("BYBIT")
```

### For Code That Used core.store.PriceStore

**Old code:**
```python
from core.store import PriceStore

store = PriceStore()
await store.update("BYBIT", "BTC-USDT", 50000.0)
data = await store.get("BTC-USDT")
```

**New code:**
```python
from core.price_store import PriceStore

store = PriceStore()
# Note: new API requires bid/ask separately
await store.update("BYBIT", "BTC-USDT", 
                   bid=50000.0, bid_size=None,
                   ask=None, ask_size=None)
data = await store.get("BTC-USDT")
```

## How to Restore (If Needed)

If you need to restore the removed files for any reason:

1. **Using Git History:**
   ```bash
   # View this PR's changes
   git log --all --full-history -- core/storage.py core/store.py
   
   # Restore from a specific commit (replace <commit-hash>)
   git checkout <commit-hash> -- core/storage.py core/store.py
   ```

2. **Manual Recreation:**
   - The original code is preserved in this document (see "What Was Removed" section above)
   - Copy the code blocks and create new files if needed

3. **From PR Branch:**
   ```bash
   # If this PR is still available
   git checkout <pr-branch>~1 -- core/storage.py core/store.py
   ```

## Verification

After this migration, verify:

1. **Import Check:**
   ```bash
   python -c "from core.price_store import PriceStore; print('OK')"
   ```

2. **No Legacy Imports:**
   ```bash
   grep -r "from core.storage import\|from core.store import" --include="*.py" .
   # Should return no results
   ```

3. **Application Startup:**
   ```bash
   python main.py
   # Should start without import errors
   ```

## Current Status

- ✅ WebSocket clients (bybit_ws, kucoin_ws, htx_ws) already use `core.price_store`
- ✅ Main application (`main.py`) uses `core.price_store`
- ✅ Arbitrage engine (`core/arbitrage.py`) uses `core.price_store` via `store.snapshot()`
- ✅ No direct imports of legacy modules found in codebase

## Questions or Issues?

If you encounter any issues related to this migration, please:
1. Check the migration guide above
2. Review the `core/price_store.py` implementation
3. Open an issue with details about the problem
4. Reference this document: `MIGRATION_REMOVE_LEGACY_STORE.md`

---

**Migration Date:** February 1, 2026  
**PR:** WIP: Remove legacy storage modules (core/storage.py, core/store.py)  
**Status:** Completed
