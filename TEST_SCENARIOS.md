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

#### 1.4 Real-Time P&L & Equity (CRITICAL)
**Test Total P&L updates in real-time:**

1. Open a position (if none open)
2. Note initial Total P&L from Dashboard
3. Wait 30-60 seconds for price to change
4. Check API: `curl -s http://localhost:8001/api/trades/open`
5. Compare:
   - **Total P&L on Dashboard** should match **sum of unrealized_pnl_usd from open positions**
   - NOT just closed trades P&L
6. **Expected:** Total P&L changes as open position P&L changes

**Test Equity updates in real-time:**

1. With open position, note Equity from Dashboard
2. Check API: `curl -s http://localhost:8001/api/account`
3. Formula: `Equity = Balance + Unrealized_PnL`
4. **Expected:** Equity = balance_usd + sum(unrealized_pnl_usd from all open positions)
5. **NOT:** Equity calculated from closed trades only

**API Verification Commands:**
```bash
# Get account (should show real-time equity)
curl -s http://localhost:8001/api/account | jq '{balance_usd, equity_usd, unrealized_pnl_usd}'

# Get open positions (sum their unrealized_pnl_usd)
curl -s http://localhost:8001/api/trades/open | jq '[.positions[].unrealized_pnl_usd] | add'

# Verify: equity_usd should = balance_usd + sum(unrealized_pnl)
```

**Known Issue (FIXED 2026-03-08):**
- Previously: Equity was calculated from closed trades only
- Fixed: Now uses real-time unrealized P&L from open positions

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

#### 3.3 Position Visualization on Chart (CRITICAL)
**Test: Selected position shows correct lines on chart**

**Prerequisites:** Have at least one open position

**Test Steps:**
1. Go to Dashboard or Open Positions tab
2. Click on an open position to select it
3. Navigate to Charts tab (or view mini-chart)
4. Verify on the chart:
   - **Entry line** (yellow/dashed) - horizontal line at entry_price
   - **TP line** (green) - horizontal line at take_profit price
   - **SL line** (red) - horizontal line at stop_loss price
5. Changing to other symbol rest cl, tp entry lines - lines dont stay as wwe select other symbol chart

**Verification:**
- Entry price should be visible as a line on the chart
- TP should be above entry (for BUY) or below (for SELL)
- SL should be below entry (for BUY) or above (for SELL)
- **Position must be between SL and TP** (entry is between stop_loss and take_profit)
- changing to other symbol results in showing correct chart, and not lines from position open on other chart/symbol

**API Check:**
```bash
# Get position details
curl -s http://localhost:8001/api/trades/open | jq '.positions[0]'

# Expected: entry_price is between stop_loss and take_profit
# For BUY:  stop_loss < entry_price < take_profit
# For SELL: take_profit < entry_price < stop_loss
```

**Visual Check:**
- Entry line should be visible on the candlestick chart
- TP/SL lines should be at correct price levels (not shifted)
- Candles around entry price should be visible

**Test New Position:**
1. Close all positions (if any open)
2. Open a new position (e.g., BTC BUY with size 0.01)
3. Immediately select the position from the list
4. Go to Charts tab
5. Verify:
   - Entry line at current price (or slightly different)
   - TP line above entry (green)
   - SL line below entry (red)
   - All lines align with actual price values on Y-axis
   - Candles show current price range (not stale data)

**Test Close Position:**
1. Open a position (see section 4)
2. Wait 1 minute for price to change
3. Click CLOSE
4. Check: Position gone, Balance changed, Trade in history

#### 3.4 Position Selection & Line Interaction (CRITICAL)
**Test: Click position → shows lines + navigates to chart**

**Prerequisites:** At least one open position

**Test Steps:**
1. Go to Open Positions tab
2. Click on a position row (not the close button)
3. **Verify:**
   - [ ] Lines appear on chart (Entry, TP, SL)
   - [ ] View automatically navigates to that symbol's chart
   - [ ] Position is highlighted/selected in the list

**Test: Click again to hide lines**
4. Click the same position again (or click elsewhere)
5. **Verify:**
   - [ ] Lines disappear from chart
   - [ ] Position is no longer highlighted

**Test: Cancel/Discard edit hides lines**
6. Click on a position (lines appear)
7. Click "Cancel" or outside the edit area
8. **Verify:**
   - [ ] Lines disappear
   - [ ] No changes made

#### 3.5 SL/TP Editing with +/- Buttons
**Test: Edit SL/TP using +/- buttons**

1. Click on an open position to select it
2. Find SL/TP edit controls (+/- buttons)
3. **Test SL:**
   - Click "+" to increase SL
   - Click "-" to decrease SL
   - Verify SL value updates in Open Positions list
4. **Test TP:**
   - Click "+" to increase TP  
   - Click "-" to decrease TP
   - Verify TP value updates in Open Positions list
5. **API Verification:**
   ```bash
   curl -s http://localhost:8001/api/trades/open | jq '.positions[0]'
   # stop_loss and take_profit should reflect changes
   ```

#### 3.6 Drag SL/TP Lines on Chart (CRITICAL)
**Test: Drag lines on chart to adjust SL/TP**

1. Click on an open position (lines appear)
2. On the chart, locate the TP line (green dashed)
3. **Drag TP line:**
   - Click and hold on TP line
   - Drag upward (increases TP) or downward (decreases TP)
   - Release
4. **Verify:**
   - [ ] TP value in Open Positions updates in real-time
   - [ ] TP line moves to new position on chart
   - [ ] API reflects new TP: `curl -s http://localhost:8001/api/trades/open | jq '.positions[0].take_profit'`
5. **Drag SL line:**
   - Click and hold on SL line (red dashed)
   - Drag upward or downward
6. **Verify:**
   - [ ] SL value in Open Positions updates in real-time
   - [ ] SL line moves to new position on chart
   - [ ] API reflects new SL

**Real-Time Update Check:**
- While dragging, watch Open Positions list
- Values should change as you drag (not only after release)
- Chart line should follow cursor during drag

**Boundary Tests:**
- SL cannot be above entry (for BUY) or below (for SELL)
- TP cannot be below entry (for BUY) or above (for SELL)
- Visual feedback when trying to set invalid values

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

#### 4.4 Strategy Change Impact on Signals (CRITICAL)
**Test: Changing strategy should change signal values**

**Prerequisites:** Frontend loaded, signals visible

**Test Steps:**
1. On Dashboard, locate a symbol (e.g., XAU or BTC)
2. Note current signal values:
   - Signal direction (BUY/SELL/NEUTRAL)
   - Score value (e.g., "0.15")
   - TP value
   - SL value
3. Find the strategy dropdown/selector for this symbol
4. **Change strategy** to a different one (e.g., from "Adaptive Regime" to "MMS Mean-Reversion")
5. Wait for signal to refresh (may take up to 30 seconds)
6. Note NEW signal values

**Verification:**
- [ ] Signal direction may change (or stay same)
- [ ] **Score value should be DIFFERENT** from before
- [ ] **TP value should be DIFFERENT** from before
- [ ] **SL value should be DIFFERENT** from before

**API Verification:**
```bash
# Get signals before strategy change
curl -s http://localhost:8001/api/signals | jq '.signals[] | select(.symbol=="XAU")'

# After changing strategy, get signals again
curl -s http://localhost:8001/api/signals | jq '.signals[] | select(.symbol=="XAU")'
```

**Compare:**
- score: should differ between strategies
- take_profit: should differ
- stop_loss: should differ
- direction: may differ

#### 4.5 Dynamic TP/SL Calculation Verification
**Test: Verify TP/SL are calculated dynamically based on strategy**

**Test Steps:**
1. Select a symbol with a known strategy
2. Note the TP and SL values
3. Check if strategy has dynamic TP/SL:
   - Look at strategy config (if accessible)
   - Or compare TP/SL ratio to ATR or other indicators
4. **For different strategies, verify:**
   - **Adaptive Regime:** TP = entry × (1 + ATR_factor), SL = entry × (1 - ATR_factor)
   - **MMS Mean-Reversion:** TP/SL based on Bollinger Bands or envelope
   - **Other strategies:** Check if TP/SL scale with volatility

**Formulas to verify:**
```bash
# Get current price and calculate expected TP/SL
PRICE=$(curl -s http://localhost:8001/api/quote/XAU | jq -r '.price')
ATR=$(curl -s "http://localhost:8001/api/indicators/XAU?indicator=atr" | jq -r '.atr')

# Expected TP (e.g., ATR × 3 for TP)
EXPECTED_TP=$(echo "$PRICE + $ATR * 3" | bc)
EXPECTED_SL=$(echo "$PRICE - $ATR * 2" | bc)

echo "Price: $PRICE, ATR: $ATR"
echo "Expected TP: ~$EXPECTED_TP"
echo "Expected SL: ~$EXPECTED_SL"
```

**Verification:**
- [ ] TP is above entry price (for BUY signals)
- [ ] SL is below entry price (for BUY signals)
- [ ] TP/SL distance scales with volatility (higher ATR = wider TP/SL)
- [ ] TP/SL values are reasonable (not too tight, not absurdly wide)

#### 4.6 Strategy-Specific Signal Differences
**Test: Different strategies produce different signals for same market conditions**

**Test Steps:**
1. For each symbol (XAU, XAG, US100, BTC):
2. Record signal with Strategy A
3. Change to Strategy B
4. Record signal with Strategy B
5. Compare

**Expected Results:**

| Symbol | Strategy | Direction | Score | TP | SL |
|--------|----------|-----------|-------|-----|-----|
| XAU | Adaptive Regime | BUY/SELL | X.XX | XXXX | XXXX |
| XAU | MMS Mean-Reversion | BUY/SELL | X.XX | XXXX | XXXX |
| XAU | BTC v2 | BUY/SELL | X.XX | XXXX | XXXX |

**Verification:**
- [ ] At least 2 out of 4 strategies produce different directions for same symbol
- [ ] Score values differ by at least 0.1 between strategies
- [ ] TP values differ by at least 1% between strategies
- [ ] SL values differ by at least 1% between strategies

---

### 4.7 SL/TP Validation & Position Lifecycle (CRITICAL)
**Test: Invalid SL/TP values are blocked, valid values work, positions close correctly**

#### 4.7.1 Invalid SL/TP Validation
**Test: Opening position with invalid SL/TP should be blocked**

**Test Steps:**
1. Go to Dashboard with a signal visible
2. Click TRADE to open position modal
3. Try to set invalid SL/TP values:
   
   **Test Case A - SL above entry (for BUY):**
   - Entry: 50000, Current: 50000
   - Set SL: 51000 (above entry - INVALID)
   - Expected: Error "SL must be below entry price for BUY"
   
   **Test Case B - TP below entry (for BUY):**
   - Set TP: 49000 (below entry - INVALID)
   - Expected: Error "TP must be above entry price for BUY"
   
   **Test Case C - SL/TP too tight:**
   - Set SL: 49900, TP: 50100 (within 0.2% - too tight)
   - Expected: Error or warning about minimum distance
   
   **Test Case D - Negative values:**
   - Set SL: -100 (negative - INVALID)
   - Expected: Error "Invalid price"

4. **Verification:**
   - [ ] Error message appears for each invalid case
   - [ ] Position does NOT open with invalid values
   - [ ] Error is clear and helpful

**API Test:**
```bash
# Try to open position with invalid SL
curl -s -X POST http://localhost:8001/api/trade/open \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC","direction":"buy","size":0.01,"entry_price":50000,"stop_loss":51000,"take_profit":52000}'
# Expected: error response
```

#### 4.7.2 Valid SL/TP Position Opening
**Test: Opening position with valid SL/TP works**

**Test Steps:**
1. Open position with valid SL/TP:
   - Entry: current price (e.g., 50000)
   - SL: 49000 (below entry, for BUY)
   - TP: 52000 (above entry, for BUY)
2. Click CONFIRM/OPEN
3. **Verification:**
   - [ ] Position opens successfully
   - [ ] Position appears in Open Positions list
   - [ ] SL = 49000 displayed correctly
   - [ ] TP = 52000 displayed correctly
   - [ ] Balance decreased by margin

**API Verification:**
```bash
curl -s http://localhost:8001/api/trades/open | jq '.positions[] | {symbol, entry_price, stop_loss, take_profit, direction}'
```

#### 4.7.3 Edit SL/TP on Open Position
**Test: Editing SL/TP on open position works and saves correctly**

**Test Steps:**
1. Find open position in list
2. Click on position to expand/edit
3. Modify SL value:
   - Current SL: 49000
   - Click "+" or set to 48500
4. Save changes
5. **Verification:**
   - [ ] SL updated to new value in UI
   - [ ] API returns new SL: `curl -s http://localhost:8001/api/trades/open | jq '.positions[0].stop_loss'`
   - [ ] Position still open

6. Modify TP value:
   - Current TP: 52000
   - Click "+" or set to 53000
7. Save changes
8. **Verification:**
   - [ ] TP updated to new value in UI
   - [ ] API returns new TP
   - [ ] Position still open

---

## 🔴 CRITICAL BUGS FOUND (2026-03-08 03:45)

### BUG: Position Close Not Working
- **Issue:** Closing position fails - API returns 405 Method Not Allowed
- **Expected:** Click CLOSE → position closes
- **Actual:** Error in console, position stays open
- **Status:** NEEDS FIX

### BUG: TP/SL Lines Don't Hide on Deselect
- **Issue:** When deselecting a position (click Cancel or elsewhere), TP/SL/Entry lines still visible
- **Expected:** Deselect → lines disappear
- **Actual:** Lines remain visible even after deselecting
- **Status:** NEEDS FIX

### BUG: Lines Show on Wrong Charts
- **Issue:** TP/SL lines for one symbol show on charts of OTHER symbols
- **Example:** Select BTC position → XAU chart shows BTC's TP/SL lines
- **Expected:** Lines only show on the chart for the selected position's symbol
- **Actual:** Lines leak to other charts
- **Status:** NEEDS FIX

---

### Bug Fix Test (4.7.6)
**Test: Position deselect clears all lines**

1. Select a position (BTC) → lines appear on BTC chart
2. Click Cancel or deselect position
3. **Verify:**
   - [ ] TP line disappears from chart
   - [ ] SL line disappears from chart
   - [ ] Entry line disappears from chart
   - [ ] Lines don't appear on other symbol charts (XAU, XAG, US100)

**Test: Close position via API**
```bash
# Get position ID
POSITION_ID=$(curl -s http://localhost:8001/api/trades/open | jq -r '.positions[0].id')

# Try to close
curl -s -X POST http://localhost:8001/api/trade/close \
  -H "Content-Type: application/json" \
  -d "{\"position_id\":\"$POSITION_ID\"}"
```

**API Verification:**
```bash
# Before edit
curl -s http://localhost:8001/api/trades/open | jq '.positions[0] | {stop_loss, take_profit}'

# After edit - values should be different
curl -s http://localhost:8001/api/trades/open | jq '.positions[0] | {stop_loss, take_profit}'
```

#### 4.7.4 Position Auto-Close After 5.5 Minutes
**Test: Position closes after timeout (5.5 minutes)**

**Test Steps:**
1. Open a new position with small size (0.01)
2. Note: position opened at time T
3. Wait 5 minutes and 30 seconds (5.5 min)
4. **Verification:**
   - [ ] Check API: `curl -s http://localhost:8001/api/trades/open`
   - [ ] Position should be CLOSED (not in open positions)
   - [ ] Position should appear in history: `curl -s http://localhost:8001/api/trades/history`
   - [ ] Balance should be updated with P&L
   - [ ] P&L should be calculated correctly (entry vs exit price)

**Manual Close Test:**
If auto-close is not implemented, manually close:
1. Click CLOSE button on position
2. **Verification:**
   - [ ] Position removed from Open Positions
   - [ ] Position appears in Trade History
   - [ ] P&L credited to Balance
   - [ ] `curl -s http://localhost:8001/api/account | jq '.account.balance_usd'` increased

**API Verification:**
```bash
# Check position before close
BEFORE=$(curl -s http://localhost:8001/api/account | jq -r '.account.balance_usd')

# Close position manually
curl -s -X POST http://localhost:8001/api/trade/close \
  -H "Content-Type: application/json" \
  -d '{"position_id":"POSITION_ID"}'

# Check balance after
AFTER=$(curl -s http://localhost:8001/api/account | jq -r '.account.balance_usd')

echo "Balance before: $BEFORE, after: $AFTER"
# Should be different (P&L added/subtracted)
```

#### 4.7.5 Position Close Verification
**Test: Verify position actually closed correctly**

**Test Steps:**
1. After position closes (manually or by TP/SL):
2. Check Open Positions: `curl -s http://localhost:8001/api/trades/open`
   - [ ] Position NOT in list
3. Check Trade History: `curl -s http://localhost:8001/api/trades/history`
   - [ ] Position IS in history
   - [ ] entry_price matches
   - [ ] exit_price is populated
   - [ ] pnl_usd is calculated
   - [ ] closed_at timestamp exists
4. Check Balance:
   - [ ] Balance reflects the trade result
   - [ ] If profit: balance increased
   - [ ] If loss: balance decreased

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

