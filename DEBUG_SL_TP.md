# Debug Report: BUY Trades Closing Immediately

## Problem Statement
User reports: "każdy buy trade jest od razu zamykany z jakąś niedorzeczną stratą nie wynikającą z ceny na wykresie"

## Root Cause Analysis

### 1. Default SL/TP Calculation (main.py lines ~1060-1066)
```python
atr = entry_price * 0.01  # 1% of price
if direction == "buy":
    tp = entry_price + (atr * 3)  # +3%
    sl = entry_price - (atr * 2)  # -2%
```

For XAU @ $2900:
- ATR = $29
- TP = 2900 + 87 = $2987 (+3%)
- SL = 2900 - 58 = $2842 (-2%)

**Problem**: For CFDs with leverage x20, a 2% move is 40% of margin! This might be too tight.

### 2. Auto-Close Logic (broker_sim.py lines ~175-195)
```python
if pos["direction"] == "buy":
    if tp and price >= tp:
        to_close.append((pos["id"], tp, "TP"))
    elif sl and price <= sl:
        to_close.append((pos["id"], sl, "SL"))
```

Every 5 seconds (`auto_trade_loop`) prices are checked. If price has any volatility, SL/TP may trigger immediately.

### 3. P&L Calculation Bug? (broker_sim.py lines ~132-136)
```python
if position["direction"] == "buy":
    pnl_usd = (exit_price - position["entry_price"]) * position["size"] * pos_leverage
else:
    pnl_usd = (position["entry_price"] - exit_price) * position["size"] * pos_leverage
```

Formula looks correct BUT: `size` is in lots (0.003), so actual P&L = price_diff * 0.003 * 20 = price_diff * 0.06

For $10 price move: P&L = $0.60 (seems wrong?)

**Wait**: For XAU/USD CFD, 1 lot = 100 oz. So 0.003 lot = 0.3 oz.
P&L = (exit - entry) * oz * leverage = $10 * 0.3 * 20 = $60 ✓

Formula seems correct, but let's verify `size` field meaning.

### 4. Frontend Edit Bug (OpenPositionsSummary.tsx lines ~35-38)
```typescript
const SYMBOL_CONFIG: Record<string, SymbolConfig> = {
  XAU: { step: 0.1, min: 2500, max: 3500, decimals: 1 },
  ...
};
```

**Problem**: If user edits SL/TP and enters value outside range, it gets clamped.
Also `editSl.toFixed(2)` with decimals=1 is inconsistent.

### 5. Input Decimal Bug (OpenPositionsSummary.tsx)
```typescript
<input 
  type="number" 
  value={editSl.toFixed(2)}  // Forces 2 decimals even if symbol needs 1
  onChange={(e) => setEditSl(parseFloat(e.target.value) || 0)}
/>
```

**Problem**: `type="number"` + decimal values can cause cursor jumping issues in React.

## Recommendations

1. **Log actual SL/TP values** when position is opened
2. **Add 5-second delay** before first price check after opening
3. **Fix input to use symbol.decimals** instead of hardcoded 2
4. **Verify P&L calculation** matches expected CFD contract specs
5. **Check if spread is accounted for** - entry at ask, exit at bid?

## Quick Test
Open XAU BUY manually and check:
1. What SL/TP values are actually set?
2. What's current price from API?
3. Does it immediately close in `update_prices`?
