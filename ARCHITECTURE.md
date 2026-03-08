# CFD Trading Bot - Architecture Documentation

## Overview
Real-time CFD trading bot with signal generation, position management, and React frontend.

---

## Backend Structure (`/backend`)

### Entry Point
**`main.py`** - FastAPI application entry
- Initializes: broker, database, trading engine, market data
- Starts: `auto_trade_loop` + `price_cache_loop` as background tasks
- Handles: graceful shutdown

---

### Services Layer (`/services`)

| File | Purpose | Key Functions |
|------|---------|---------------|
| `state.py` | **Central state management** - single source of truth for all global state | `get_account()`, `get_open_positions()`, `set_account()`, `get_instruments()` |
| `trading_engine.py` | Main trading logic + signal generation | `auto_trade_loop()`, `_analyze_single_symbol()`, `_async_update_prices()` |
| `market_data.py` | Price data fetching + caching | `update_live_price_cache()`, `_live_price_cache` dict |
| `signal_generator.py` | Technical indicator calculation | `generate_signals()` |
| `strategy_manager.py` | Strategy loading + analysis | `get_strategy()`, `analyze_with_new_strategy()` |
| `signal_cache.py` | Signal caching | `get_cached_signals()`, `set_cached_signals()` |
| `circuit_breaker.py` | API failure protection | Circuit breaker for external APIs |
| `backtest_engine.py` | Historical backtesting | `run_backtest()` |

---

### API Routes (`/api/routes`)

| File | Endpoints | Notes |
|------|-----------|-------|
| `account.py` | `/api/account` | Returns balance, equity, unrealized P&L |
| `trades.py` | `/api/trades/*`, `/api/trade/{id}/close`, `/api/trade/open` | Trade operations |
| `signals.py` | `/api/signals` | Signal generation |
| `instruments.py` | `/api/instruments` | Available trading instruments |
| `chart.py` | `/api/chart/{symbol}` | OHLCV candlestick data |
| `settings.py` | `/api/settings` | Bot configuration |
| `logs.py` | `/api/logs` | Application logs |
| `backtest.py` | `/api/backtest/*` | Backtesting endpoints |

---

### Data Models (`/models.py`)

```
Position {
    id, symbol, direction, entry_price, current_price,
    size, leverage, stop_loss, take_profit,
    opened_at, unrealized_pnl_usd
}

Account {
    balance_usd, equity_usd, unrealized_pnl_usd
}

Signal {
    symbol, direction, score, confidence, price,
    take_profit, stop_loss, generated_at
}
```

---

### Database (`/database.py`)

- **MongoDB** for persistence
- Collections: `positions`, `closed_trades`, `settings`, `logs`
- Key functions:
  - `async_save_position()`
  - `async_load_open_positions()`
  - `async_close_position()`
  - `async_sync_account_from_closed_trades()`

---

### Settings (`/settings.py`)

- `INSTRUMENTS` - Dict of supported symbols (XAU, XAG, US100, BTC)
- `INITIAL_BALANCE_USD` - Starting balance
- API keys, timeouts, etc.

---

## Frontend Structure (`/frontend`)

### Pages/Tabs
| File | Route | Purpose |
|------|-------|---------|
| `MainTab.tsx` | `/` (Dashboard) | Account overview, mini charts |
| `ChartsTab.tsx` | `/charts` | Full candlestick charts |
| `TradesTab.tsx` | `/trades` | Trade history |
| `OpenPositionsSummary.tsx` | (component) | Position list + close buttons |
| `SignalsGrid.tsx` | (component) | Signal display + trade buttons |
| `SettingsTab.tsx` | `/settings` | Configuration |

### Key Components
- `CandlestickChart.tsx` - TradingView-style chart
- `PriceChart.tsx` - Alternative chart component
- `Dashboard.tsx` - Main dashboard layout

### API Integration
- `api.ts` - Base URL: `window.location.origin + "/api"`
- Proxy configured in `vite.config.ts` → backend port 8001

---

## Data Flow

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Frontend  │────▶│   FastAPI        │────▶│  Services   │
│  (React)    │◀────│   (main.py)      │◀────│  (state.py) │
└─────────────┘     └──────────────────┘     └─────────────┘
                           │                        │
                           ▼                        ▼
                    ┌─────────────┐     ┌──────────────────┐
                    │  Database    │     │  Market Data      │
                    │  (MongoDB)  │     │  (Finnhub)       │
                    └─────────────┘     └──────────────────┘
```

---

## Known Issues & Improvements

### 🔴 Critical Issues

1. **✅ FIXED: Price Cache Not Updating**
   - Now uses broker's current_price directly (working)

2. **✅ FIXED: Import Order Bug**
   - `dotenv.load_dotenv()` was called AFTER database import
   - Fixed: moved load_dotenv() to top of main.py
   - MongoDB now connects properly

3. **Backend Crashes Frequently**
   - No PM2/systemd process manager
   - Needs auto-restart mechanism

4. **✅ FIXED: strategy/risk.py import bug**
   - `import math` was at line 81 but used at line 70
   - Fixed: moved import to top of file

5. **✅ FIXED: Duplicated P&L calculation in state.py**
   - Removed duplicate code block

### 🟡 Performance Issues

1. **Signal Generation is Slow**
   - `generate_signals()` takes ~5 seconds per iteration
   - Called every 5 minutes in auto-trade loop
   - Could be optimized with caching

2. **MongoDB in Same Process**
   - `database.py` operations are synchronous
   - Should use async MongoDB driver properly

3. **No Rate Limiting**
   - Frontend can spam API calls
   - Need request throttling

### 🟡 Code Duplication

1. **Equity Calculation Duplicated**
   - `services/state.py::get_account()` calculates equity
   - `api/routes/account.py` also calculates (different logic)
   - Should use single source

2. **Position P&L Calculation**
   - Multiple places calculate unrealized P&L
   - `broker_sim.py`, `state.py`, frontend all do it

3. **API Response Format Inconsistent**
   - Some endpoints return `{data: []}`, others `{candles: []}`
   - Causes frontend mapping bugs

### 🟢 Good Practices Already

- Single state in `state.py` ✅
- Broker pattern for trading ✅
- Circuit breaker for external APIs ✅

---

## Port Configuration

| Service | Port | Notes |
|---------|------|-------|
| Backend | 8001 | FastAPI |
| Frontend | 5173 | Vite dev server |
| MongoDB | 27017 | External |

---

## Next Steps

1. Fix price_cache_loop to actually populate cache
2. Add process manager (PM2) for backend
3. Consolidate equity/P&L calculations
4. Standardize API response format
5. Add rate limiting to API
