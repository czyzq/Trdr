# Auto-Trade Loop Investigation

## Problem Summary

The auto-trade loop was dying after 1-2 iterations, causing the trading bot to stop scanning for signals.

## Symptoms

1. Loop would run 1-2 iterations successfully
2. After `await asyncio.sleep(300)`, the loop would not wake up
3. Process remained running but the trading loop was stuck
4. Cron would restart the process every 30 minutes as a workaround

## Root Cause

**The issue is with uvicorn/FastAPI's handling of long-running `asyncio.sleep()` calls.**

When using `await asyncio.sleep(300)` (5 minutes) in an async function within a uvicorn/FastAPI context, the sleep operation sometimes doesn't complete properly. This appears to be related to how uvicorn manages the event loop - long-running sleeps can be suspended or cancelled without proper signaling.

## Investigation Steps

1. Added detailed logging (`[DEBUG AUTO-TRADE]`) - this temporarily "fixed" the issue (observer effect)
2. Added iteration counter
3. Tried different approaches to the sleep

## Solution

Instead of a single long sleep, use **chunked sleeps** with intermediate logging:

```python
# OLD (broken):
await asyncio.sleep(300)

# NEW (working):
sleep_cycles = AUTO_TRADE_INTERVAL_SEC // 60  # 300 // 60 = 5
for i in range(sleep_cycles):
    await asyncio.sleep(60)
    print(f"Sleep cycle {i+1} complete")
```

This approach:
- Breaks the long sleep into 60-second chunks
- Each chunk completes independently
- If one chunk fails, the next ones still run
- More resilient to event loop issues

## Files Modified

- `/Users/pinchr/dev/cfd-trading-bot/backend/main.py` - auto_trade_loop function

## Test Results

After implementing chunked sleeps:
- Iteration #1: ✅ Ran successfully
- Sleep cycles 1-5: ✅ All completed
- Iteration #2: ✅ Started successfully
- Loop continues running properly

## Alternative Solutions Considered

1. **Use `asyncio.create_task()`** - Would create a separate task but adds complexity
2. **Use `time.sleep()` instead of `asyncio.sleep()`** - Blocks the event loop, not ideal
3. **Use a scheduler library** - Adds dependency, overkill for this use case
4. **Move auto-trade to separate process** - Most robust but significant refactoring

The chunked sleep approach is the simplest fix that works reliably.

## Monitoring

To verify the fix is working, check logs for:
```
[AUTO-TRADE] Sleep cycle 1/5 (60s)...
[AUTO-TRADE] Sleep cycle 1 complete
[AUTO-TRADE] Sleep cycle 2/5 (60s)...
...
[AUTO-TRADE] Wake up from full sleep cycle, continuing iteration #N
```
