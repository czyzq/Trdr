# Current Active Strategy Configuration
**Last updated: 2026-02-17**

## Active Strategies

| Strategy | Status | Allocation | Symbols |
|----------|--------|------------|---------|
| AdaptiveRegime | ENABLED | 60% | XAU, XAG, US100 |
| MMS | ENABLED | 40% | XAU, XAG |

## Current Risk Settings

```
Max leverage: x2 (MMS ladder: x0.01 to x2)
Max position size: 5% account per trade
Max daily loss: 3% account (circuit breaker)
Max drawdown: 10% from peak (hard stop)
Correlation limit: 0.7 (no correlated positions)
```

## Symbol Configuration

### XAU/USD (Gold)
- Min score: 0.15
- Trailing stop: YES (trending mode)
- Timeframes: 1h, 4h
- ATR multiplier: SL 1.5x, TP 3.0-3.5x

### XAG/USD (Silver)
- Min score: 0.15
- Trailing stop: YES
- Timeframes: 1h, 4h
- ATR multiplier: SL 1.5x, TP 3.0x

### US100 (Nasdaq)
- Min score: 0.20
- Trailing stop: NO (mean reversion bias)
- Timeframes: 1h, 4h
- ATR multiplier: SL 2.0x, TP 4.0x

## Known Issues (Active)

- ~~[FIXED] Missing `await` in auto_trade_loop~~ — VERIFIED 2026-02-17: All broker.open_position() calls have await at lines 1006, 1307
- ~~[FIXED] broker._async_update_prices() sync/async mismatch~~ — VERIFIED 2026-02-17: Properly awaited at lines 680, 930
- ~~[FIXED] MMS sequentiality not persisted to DB~~ — VERIFIED 2026-02-17: Loads from DB on startup via init_mms_states_from_db(), saves on every trade result
- ~~[FIXED] Port 8001/8002 mismatch~~ — Fixed 2026-02-17: Standardized on port 8001

## Code Health Status

**All critical async/await bugs RESOLVED.**
- 0 errors in event logs
- All broker calls properly awaited
- MMS state persistence working
- Server ready to start

## Last 24h Performance

- Trades: 0 (market closed / no signals)
- Win rate: N/A
- PnL: 0.00%
- Open positions: 2 (from previous sessions)
