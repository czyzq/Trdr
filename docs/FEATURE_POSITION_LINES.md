# Feature: Position Lines & SL/TP Sliders

## Cel

Dodać wizualne wskazówki dla otwartych pozycji na wykresie:
- Linie Entry, TP, SL jako przerywane linie przez cały wykres
- Suwaki do przesuwania TP/SL
- Panel po prawej stronie z wartościami

## UI Specification

### 1. Chart Area (CandlestickChart.tsx)

**Selected Position Lines:**
- Entry: solid green (buy) / red (sell) line
- TP: dashed green line 
- SL: dashed red line
- Lines span entire chart height
- Hover on line shows tooltip with price

**Implementation:**
- Use TradingView's `createChart()` with `lineSeries`
- Add horizontal lines at entry/tp/sl prices
- Color based on direction (green=buy, red=sell)
- Dashed style for TP/SL

### 2. Right Side Panel

**Position Details Panel:**
```
┌─────────────────────┐
│ 📍 XAU BUY         │
│ Entry: $5200.00    │
│ ─────────────────  │
│ 🎯 Take Profit     │
│ [$5150] ──●── [$5300] │
│ Current: $5250    │
│ ─────────────────  │
│ 🛡️ Stop Loss      │
│ [$5100] ──●── [$5200] │
│ Current: $5150    │
│ ─────────────────  │
│ 💰 P&L: +$50 (+1%)│
│ ⏱️ Duration: 2h    │
│                     │
│ [Confirm Changes]   │
│ [Close Position]    │
└─────────────────────┘
```

### 3. Sliders

**TP Slider:**
- Range: entry ± 10%
- Step: $1 or 0.1%
- Drag to change TP
- Preview line on chart while dragging

**SL Slider:**
- Range: entry ± 5%
- Step: $1 or 0.1%
- Drag to change SL  
- Preview line on chart while dragging

### 4. Confirmation Flow

```
User drags slider → Line moves on chart → Tooltip shows "Unconfirmed"
User releases → Modal: "Confirm TP/SL change?"
  [Cancel] → Revert to original
  [Confirm] → Send API request → Update position
```

## API Endpoints

Existing:
- `POST /api/trade/adjust/{position_id}` - adjust TP/SL
- `POST /api/trade/close/{position_id}` - close position

Need:
- `GET /api/trades/open` - already exists

## Components to Modify

1. **CandlestickChart.tsx** - Add position lines
2. **OpenPositionsSummary.tsx** - Add sliders panel
3. **Dashboard.tsx** - Wire up state

## State Management

```typescript
interface PositionState {
  selectedPositionId: string | null;
  pendingTp: number | null;
  pendingSl: number | null;
  isDragging: boolean;
}
```

## Implementation Steps

1. Add position lines to chart (dashed horizontal lines)
2. Create PositionDetailsPanel component
3. Add sliders with real-time preview
4. Add confirmation modal
5. Wire up API calls

## Files

- `/Users/pinchr/dev/cfd-trading-bot/frontend/src/components/CandlestickChart.tsx`
- `/Users/pinchr/dev/cfd-trading-bot/frontend/src/components/PositionDetailsPanel.tsx` (new)
- `/Users/pinchr/dev/cfd-trading-bot/frontend/src/components/OpenPositionsSummary.tsx`
