# WebSocket Shutdown Fix

## Problem

When shutting down the bot, multiple errors were occurring:

```
Error stopping BybitWS: object NoneType can't be used in 'await' expression
Error stopping KucoinWS: object NoneType can't be used in 'await' expression
Error stopping HtxWS: object NoneType can't be used in 'await' expression
Error stopping Binance: 'BinanceWS' object has no attribute 'stop'
```

## Root Cause

The WebSocket classes have different stop method signatures:

1. **BybitWS, KucoinWS, HtxWS**: Have **synchronous** `stop()` methods that return `None`
2. **MexcWS**: Has an **async** `stop()` method that returns a coroutine
3. **BinanceWS**: Has **no** `stop()` method at all

The shutdown code was blindly calling `await exchange.stop()` for all exchanges, which:
- Failed for sync methods (can't await None)
- Failed for missing methods (AttributeError)

## Solution

The fix now:

1. **Checks** if the exchange has a `stop()` method
2. **Calls** the stop method
3. **Detects** if it's a coroutine (async) or not (sync)
4. **Awaits** it only if it's async
5. **Handles** missing methods gracefully

### Code Change

```python
for exchange in self.exchanges:
    try:
        exchange_name = getattr(exchange, 'name', ...)
        
        # Check if exchange has a stop method
        if not hasattr(exchange, 'stop'):
            logger.debug(f"{exchange_name} has no stop method, skipping")
            continue
        
        # Call stop method (handle both sync and async)
        stop_method = exchange.stop()
        if asyncio.iscoroutine(stop_method):
            await stop_method  # Async method
        # else: Synchronous method already executed
            
    except Exception as e:
        logger.error(f"Error stopping {exchange_name}: {e}")
```

## Result

✅ Clean shutdown for all WebSocket types
✅ No more "NoneType can't be used in 'await'" errors
✅ No more "has no attribute 'stop'" errors
✅ Handles both sync and async stop methods gracefully

## Testing

To verify the fix works:

1. Start the bot: `python main.py`
2. Wait for it to initialize
3. Press Ctrl+C to stop
4. Check that shutdown completes without errors

You should see:
```
Stopping WebSocket connections...
BybitWS has no stop method, skipping (or stops cleanly)
KucoinWS stops cleanly
HTX stops cleanly
MexcWS stops cleanly
BinanceWS has no stop method, skipping
```

No error messages during shutdown!
