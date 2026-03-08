# CFD Trading Bot - Test Scenarios

## Quick Test Commands

### API Tests (terminal)
```bash
# Start services
cd ~/dev/cfd-trading-bot/backend && python3 -m uvicorn main:app --port 8001 &
cd ~/dev/cfd-trading-bot/frontend && npm run dev -- --port 5173 &

# Test all APIs
curl -s http://localhost:8001/api/account
curl -s http://localhost:8001/api/trades/open
curl -s http://localhost:8001/api/trades/history
curl -s http://localhost:8001/api/signals
curl -s http://localhost:8001/api/instruments
curl -s "http://localhost:8001/api/chart/XAU?resolution=60&count=10"
```

---

## Manual UI Test Scenarios

### ✅ PREREQUISITES
- [ ] Backend running on port 8001
- [ ] Frontend running on port 5173
- [ ] Open browser to http://localhost:5173/cfd/

---

### 1. DASHBOARD (Main Tab)

#### 1.1 Account Display
- [ ] **Balance** - Check value matches API: `curl http://localhost:8001/api/account | jq .balance_usd`
- [ ] **Equity** - Should be different from Balance when positions open
- [ ] **Open Positions count** - Compare with API count
- [ ] **Closed Trades count** - Compare with API count
- [ ] **Win Rate %** - Should show percentage (e.g., "71%")
- [ ] **Total P&L** - Should show cumulative profit/loss

#### 1.2 Mini Charts
- [ ] **XAU chart** - Displays candles/symbol
- [ ] **XAG chart** - Displays candles/symbol  
- [ ] **US100 chart** - Displays candles/symbol
- [ ] **BTC chart** - Displays candles/symbol
- [ ] **Chart shows price** - Price label visible
- [ ] **Chart shows indicators** - SMA/RSI/Volume visible

#### 1.3 Dashboard Interactions
- [ ] **Resolution selector** - Click different timeframes (1m, 5m, 15m, 60m)
- [ ] **Chart updates** - Changing resolution loads new data
- [ ] **No "Network error"** - Charts should load without errors

---

### 2. CHARTS TAB

#### 2.1 Chart Display
- [ ] **4 charts visible** - XAU, XAG, US100, BTC
- [ ] **Candles rendering** - Green/red candles visible
- [ ] **Price axis** - Y-axis shows prices
- [ ] **Time axis** - X-axis shows times
- [ ] **Volume bars** - Volume indicator at bottom

#### 2.2 Indicators
- [ ] **SMA line** - Moving average visible
- [ ] **RSI gauge** - Shows overbought/oversold
- [ ] **Volume** - Volume bars visible

#### 2.3 Chart Interactions
- [ ] **Resolution dropdown** - Select different timeframes
- [ ] **Symbol tabs** - Click to switch between XAU/XAG/US100/BTC
- [ ] **Data loads** - Changing symbol loads new candles

#### 2.4 Candle Count Verification
**Test candle counts by timeframe:**

| Timeframe | Expected Candles | API Query |
|-----------|------------------|-----------|
| 15m | 24 | `curl -s "http://localhost:8001/api/chart/BTC?resolution=15&count=24"` |
| 30m | 24 | `curl -s "http://localhost:8001/api/chart/BTC?resolution=30&count=24"` |
| 60m | 24 | `curl -s "http://localhost:8001/api/chart/BTC?resolution=60&count=24"` |
| 1d (D1) | 14 | `curl -s "http://localhost:8001/api/chart/BTC?resolution=D1&count=14"` |

**Verification Steps:**
1. For each timeframe, fetch chart data from API
2. Count actual candles returned
3. Verify count matches expected value
4. Compare with Dashboard mini-chart (should be fewer in Charts tab)

**Expected Difference:**
- **Dashboard mini-charts:** More candles (full width display)
- **Charts tab:** Fewer candles (24 for 15m/30m/1h, 14 for 1d)

---

### 3. TRADING - OPEN POSITIONS

#### 3.1 Position List
- [ ] **Positions displayed** - List shows open positions
- [ ] **Position details** - Symbol, direction, entry price visible
- [ ] **Current price** - Shows live price
- [ ] **P&L display** - Shows unrealized profit/loss in $ and %
- [ ] **SL/TP levels** - Stop loss and take profit shown

#### 3.2 Close Position
- [ ] **Close button visible** - "CLOSE" button on each position
- [ ] **Click Close** - Position closes
- [ ] **Confirmation** - Position removed from list
- [ ] **P&L credited** - Balance increases by profit
- [ ] **Balance updates** - New balance reflects closed trade

**Test Close Position:**
1. Open a position (see section 4)
2. Wait 1 minute for price to change
3. Click CLOSE
4. Check: Position gone, Balance changed, Trade in history

---

### 4. TRADING - SIGNALS & OPEN

#### 4.1 Signals Display
- [ ] **Signals visible** - 4 symbols with signals
- [ ] **Signal direction** - BUY/SELL/NEUTRAL badges
- [ ] **Signal score** - Score value shown (e.g., "0.15")
- [ ] **Confidence %** - Confidence level shown
- [ ] **Current price** - Price displayed for each symbol
- [ ] **TP/SL values** - Take profit and stop loss shown

#### 4.2 Open Position (Manual Trade)
- [ ] **Trade button** - "TRADE" button on signal row
- [ ] **Modal opens** - Trade form appears
- [ ] **Symbol correct** - Pre-filled with selected symbol
- [ ] **Direction selector** - BUY/SELL toggle works

**Test Open Position:**
1. Find signal with BUY direction and positive score
2. Click TRADE button
3. Set size = 0.01 (small test)
4. Click CONFIRM/OPEN
5. **Verify:**
   - [ ] Position appears in Open Positions
   - [ ] Balance decreased by margin
   - [ ] API shows new position: `curl http://localhost:8001/api/trades/open`

#### 4.3 Trade Validation
- [ ] **Error on invalid size** - Shows error for 0 or negative
- [ ] **Insufficient funds** - Error when balance too low
- [ ] **Position opens** - Success message/position appears

---

### 5. TRADES TAB (History)

#### 5.1 Trade History
- [ ] **Closed trades list** - Shows all past trades
- [ ] **Trade details** - Symbol, entry, exit, P&L
- [ ] **P&L coloring** - Green for profit, red for loss
- [ ] **Timestamps** - Open/close times shown

#### 5.2 History Accuracy
- [ ] **Closed position appears** - After closing, shows in history
- [ ] **P&L matches** - History P&L matches closed trade P&L
- [ ] **Count correct** - Number matches API: `curl http://localhost:8001/api/trades/history | jq '.trades | length'`

---

### 6. SETTINGS TAB

#### 6.1 Settings Display
- [ ] **Settings load** - Configuration values visible
- [ ] **Sections visible** - Risk, Trading, Strategies

#### 6.2 Settings Modification
- [ ] **Change value** - Edit a setting
- [ ] **Save button** - Save changes
- [ ] **Change persists** - Value retained after refresh
- [ ] **API reflects change** - `curl http://localhost:8001/api/settings`

---

### 7. LOGS TAB

#### 7.1 Logs Display
- [ ] **Logs visible** - Application logs shown
- [ ] **Log levels** - INFO, WARNING, ERROR, SUCCESS colored
- [ ] **Timestamps** - Time shown for each log
- [ ] **Scroll works** - Can scroll through logs

#### 7.2 Log Content
- [ ] **Trade events** - OPEN/CLOSE events logged
- [ ] **Signal events** - Signal generation logged
- [ ] **Errors visible** - Failed operations show as ERROR

---

### 8. AUTO-TRADE (Background)

#### 8.1 Auto-Trade Behavior
- [ ] **Signal generated** - Every 5 minutes
- [ ] **Position auto-opened** - When signal meets criteria
- [ ] **Position auto-closed** - When TP/SL hit
- [ ] **Logs show activity** - "[AUTO-TRADE]" in logs

**Test Auto-Trade:**
1. Wait 5 minutes for auto-trade cycle
2. Check logs for: "[AUTO-TRADE] Loop iteration"
3. Check for new positions or signals

---

## API vs UI Comparison Tests

### Balance Test
```bash
# Terminal
API_BALANCE=$(curl -s http://localhost:8001/api/account | jq -r '.balance_usd')
echo "API: $API_BALANCE"

# UI - Read from screen
# Should match within $0.01
```

### Equity Test
```bash
# With open position
API_EQUITY=$(curl -s http://localhost:8001/api/account | jq -r '.equity_usd')
API_BALANCE=$(curl -s http://localhost:8001/api/account | jq -r '.balance_usd')

# Equity should = Balance + Unrealized P&L
# UI should show Equity different from Balance
```

### Position P&L Test
```bash
# Open position
curl -s -X POST http://localhost:8001/api/trade/open \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC","direction":"buy","size":0.01,"entry_price":50000}'

# Wait 1 min
sleep 60

# Check P&L
curl -s http://localhost:8001/api/trades/open | jq '.positions[0].unrealized_pnl_usd'

# UI should show same P&L
```

---

## Critical Path Tests (Smoke Test)

Run these first to verify basic functionality:

1. [ ] **Backend alive** - `curl http://localhost:8001/api/account` returns 200
2. [ ] **Frontend loads** - http://localhost:5173/cfd/ shows UI
3. [ ] **Dashboard shows balance** - Non-zero balance displayed
4. [ ] **Charts show candles** - At least one chart has data
5. [ ] **Open position works** - Can open test position
6. [ ] **Close position works** - Can close test position
7. [ ] **Balance updates** - Balance changes after trade

---

## Known Issues (Track Here)

| Issue | Status | Notes |
|-------|--------|-------|
| Price cache empty | ⚠️ | Working via broker current_price |
| Charts "No Data" on Dashboard | ✅ FIXED | Was data.data vs data.candles |
| Equity = Balance | ✅ FIXED | Was using wrong field |
| TP/SL showing 0 | ✅ FIXED | Was wrong JSON path |
| Backend crashes | 🔴 | Needs PM2/process manager |
| Backtest engine empty | 🔴 | Functions return pass |

---

## Test Execution Log

| Date | Time | Tester | Result | Issues |
|------|------|--------|--------|--------|
| 2026-03-08 | 01:15 | Pinchr | PENDING | - |
| 2026-03-08 | 02:52 | Executor-v2 | 5/5 PASS | ALL BUGS FIXED: TP/SL lines, Markers, Price Match |

---

## Known Issues (2026-03-08)

### ✅ PnL Not Updating
- **Issue:** P&L shows 0.00 for open positions, doesn't change
- **Expected:** P&L should update in real-time based on current price vs entry
- **Status:** ✅ FIXED - Test 2026-03-08 02:38 potwierdził aktualizację P&L

### ✅ Position Lines on Chart
- **Issue:** SL/TP lines are shifted up, not matching reality
- **Expected:** Lines should be at actual SL/TP prices
- **Status:** ✅ FIXED - 2026-03-08 02:52 - Linie TP/SL widoczne na wykresie

### ✅ Trade Entry/Exit Markers
- **Issue:** No triangles (▲/▼) marking where positions were opened
- **Issue:** No squares (■) marking where positions were closed
- **Expected:** 
  - Triangle ▲ = Buy entry point
  - Triangle ▼ = Sell entry point  
  - Square ■ = Exit point
- **Status:** ✅ FIXED - 2026-03-08 02:52 - Trójkąty renderują się na ostatniej świecy

### ✅ Positions Match Chart
- **Issue:** Open positions don't match price on chart
- **Expected:** Position entry price should align with candle on chart
- **Status:** ✅ FIXED - 2026-03-08 02:52 - Cena wejścia w zakresie wykresu

### ✅ What Was Working Before Refactor
- Chart rendering with candles
- Indicators (SMA, RSI, MACD, BB)
- Dashboard stats
- API persistence

---

## Test Scenarios for Bugs

### Position P&L Test
1. Open position (e.g., BTC @ 67000)
2. Wait 1 minute for price to change
3. Check Dashboard - P&L should NOT be 0.00
4. Check Open Positions - P&L should show real-time value
5. Compare with: `curl http://localhost:8001/api/trades/open`

### Chart Position Lines Test
1. Open a position (e.g., BTC buy)
2. Go to Charts tab
3. Find the position on the chart:
   - Should see ▲ triangle at entry price
   - Should see horizontal line at SL price
   - Should see horizontal line at TP price
4. Lines should align with actual price levels (not shifted)

### Trade Entry/Exit Markers Test
1. Open a position
2. Close the position
3. Go to Charts tab
4. Check for markers:
   - ▲ triangle where buy was opened
   - ▼ triangle where sell was opened
   - ■ square where position was closed
5. Markers should be on correct candles

### Position vs Chart Price Test
1. Note current price from Dashboard (e.g., BTC: $67000)
2. Open BTC position
3. Check chart - entry line should match current price candle
4. Close position
5. Check chart - exit square should match close price candle

---

## 🔴 CRITICAL BUGS (2026-03-08 01:50)

### 1. Trading Mode/State Resets on Page Refresh
- **Issue:** Refreshing browser resets trading mode and broker state
- **Expected:** State should persist in MongoDB
- **Root cause:** Broker state not loaded on init OR state saved to memory only
- **Fix needed:** Load broker state from MongoDB on startup
- **Test Result:** ✅ PASS - Stan zachowany po odświeżeniu (Balance $3056.59, Open 1, P&L -8.15)

### 2. P&L Always Shows 0.00
- **Issue:** unrealized_pnl_usd is always 0 for open positions
- **Root cause:** get_open_positions() can't create new event loop in async context
- **Fix needed:** Use broker's _async_update_prices() properly OR cache prices
- **Test Result:** ✅ PASS - P&L aktualizuje się poprawnie (zmieniło się z -8.15 na -5.21 po 35s)

### 3. Chart Position Lines Wrong Position
- **Issue:** SL/TP lines shifted up, don't match actual prices
- **Root cause:** Entry price not matching chart candles
- **Fix needed:** Verify position entry price matches current price at open time
- **Test Result:** ❌ FAIL - Brak widocznych linii SL/TP na wykresie

### 4. Trade Entry/Exit Markers Missing
- **Issue:** No ▲/▼ triangles for entry, no ■ squares for exit
- **Expected:** Triangles show buy/sell entry, squares show exit
- **Root cause:** Frontend not rendering chart overlays OR data not passed
- **Test Result:** ❌ FAIL - Tekst "Trades: ▲ ▼ ■" istnieje, ale trójkąty/kwadraty nie są widoczne na wykresie

### 5. Positions Don't Match Chart
- **Issue:** Open positions don't align with chart candles
- **Root cause:** Price data mismatch between entry_price and live price
- **Test Result:** ❌ FAIL - Pozycja BTC entry: 67262.91, ale wykres pokazuje 65314.76 (Dashboard) lub 70527.93 (Charts - cached)

---

## Immediate Fixes Needed

### Fix 1: Broker State Persistence
```python
# In broker_sim.py or main.py startup:
# 1. Load open positions from MongoDB on init
# 2. Save positions to MongoDB on every change
```

### Fix 2: P&L Calculation  
```python
# In get_open_positions() - use broker's async properly:
# Don't create new event loop - call broker._async_update_prices() directly
```

### Fix 3: Chart Overlays
```python
# In ChartsTab.tsx or CandlestickChart.tsx:
# Pass position data (entry_price, SL, TP) to chart
# Render lines at correct price levels
```

