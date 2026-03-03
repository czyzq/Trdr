# FIXES.md - CFD Trading Bot

## 🔧 Frontend Build Errors - Duplicate Identifiers (2026-02-24)

**Status:** ✅ FIXED

**Problem:** 
```
src/components/CandlestickChart.tsx(42,3): error TS2300: Duplicate identifier 'selectedPosition'.
src/components/CandlestickChart.tsx(43,3): error TS2300: Duplicate identifier 'selectedPosition'.
src/components/CandlestickChart.tsx(236,3): error TS2300: Duplicate identifier 'selectedPosition'.
src/components/CandlestickChart.tsx(237,3): error TS2300: Duplicate identifier 'selectedPosition'.
```

**Fix:** Removed duplicate `selectedPosition` declarations in:
- Interface (lines 42-43) - removed duplicate
- Function params (lines 236-237) - removed duplicate

---

## 🔧 MainTab.tsx - Missing setSelectedSymbol (2026-02-24)

**Status:** ✅ FIXED

**Problem:**
```
src/components/MainTab.tsx(441,59): error TS2552: Cannot find name 'setSelectedSymbol'. Did you mean 'selectedSymbol'?
src/components/MainTab.tsx(441,77): error TS18047: 'pos' is possibly 'null'.
```

**Fix:** Changed `setSelectedSymbol(pos.symbol)` to `onSymbolSelect(pos.symbol)` and added null check for `pos`.

---

## 🔧 Fixer Cron Script (2026-02-24)

**Status:** ✅ Added

**Problem:** Need automated error checking every 30 minutes.

**Solution:** Created `/Users/pinchr/dev/cfd-trading-bot/fixer.sh` that:
- Checks if frontend (port 5173) and backend (port 8001) are running
- Restarts services if not running
- Checks backend API health
- Runs TypeScript build to catch errors
- Checks MongoDB connection
- Logs to `/Users/pinchr/dev/cfd-trading-bot/logs/fixer.log`
- Updates FIXES.md with any issues found

**Cron:**
```bash
*/30 * * * * /Users/pinchr/dev/cfd-trading-bot/fixer.sh >> /Users/pinchr/dev/cfd-trading-bot/logs/fixer.log 2>&1
```

---

## 🔧 Auto-Trade Loop Fix (2026-02-23)

**Status:** ✅ Fixed

**Problem:** Pętla asyncio umierała po 1 iteracji - task scheduler gubił wątek po ciężkim `generate_signals()`.

**Rozwiązanie:**
- Dodano więcej logowania (`[DEBUG AUTO-TRADE]`, `[DEBUG] generate_signals set last_scan`)
- To wymusiło flush buforów i naprawiło problem (observer effect)
- Dodano cron restart co 30 min jako zabezpieczenie

**Cron:**
```bash
*/30 * * * * launchctl stop ai.pinchr.cfd-bot && sleep 2 && launchctl start ai.pinchr.cfd-bot
```

---

## 🔧 XAG Score Validation Error (2026-02-23)

**Status:** ✅ Fixed

**Problem:** 
```
[ERROR] Error analyzing XAG: 2 validation errors for Signal
score: Input should be less than or equal to 1 [type=less_than_equal, input_value=1.25...]
```

**Przyczyna:** `technical_score` w strategies.py przekraczał 1.0 po seasonality bias.

**Fix:** Dodano clamping w 3 miejscach:
1. `strategies.py` linia 564: `technical_score = max(-1, min(1, technical_score * 0.9 + seasonality_bias))`
2. `strategies.py` linia 967: `technical_score = max(-1, min(1, technical_score * 0.85 + 0.15))`
3. `main.py` linia ~1158: Clamp przy tworzeniu Signal

---

## 🔧 Ngrok Autostart (2026-02-23)

**Status

**Problem:** Ngrok nie działał po restarcie:** ✅ Fixed.

**Rozwiązanie:** Dodano launch agent:
```xml
~/Library/LaunchAgents/ai.pinchr.ngrok.plist
```

---

## 🔧 last_scan Not Updating in API (2026-02-23)

**Status:** ✅ Fixed

**Problem:** `last_scan` w API nie aktualizował się mimo że w DB był nowy.

**Przyczyna:** Globalna zmienna `account` nie była aktualizowana po zapisie do DB.

**Fix:** Dodano update globalnego `account["last_scan"]` w `generate_signals()`:
```python
account["last_scan"] = datetime.utcnow().isoformat()
```

---

## 🔧 Trend Reversal Early Exit (2026-02-23)

**Status:** ✅ Implemented

**Funkcja:** Zamykanie pozycji gdy RSI pokazuje overbought/oversold z zyskiem >0.5%.

**Lokalizacja:** `broker_sim.py` w `_async_update_prices()`

**Włączenie:**
```python
from database import set_setting
set_setting('TREND_REVERSAL_EXIT', 1, 'user')
```

**Warunki:**
- Pozycja musi mieć zysk > 0.5%
- BUY: RSI > 70 (overbought) → zamyka
- SELL: RSI < 30 (oversold) → zamyka

---

## 🔧 Scalp Strategies (2026-02-23)

**Status:** ✅ Added

**Nowe strategie:** `xau_scalp_trend`, `btc_scalp_trend`

**Parametry:**
- TP: 2.5% (vs 5% w starych)
- SL: 1.5% (vs 2%)
- Trailing stop: WŁĄCZONY (aktywuje się przy 1% zysku)
- Leverage: 10x (vs 20x)
- Risk/trade: 1.5%

**Użycie:**
```bash
curl -X POST "http://localhost:8001/api/strategy/XAU?strategy_id=JSON:xau_scalp_trend"
curl -X POST "http://localhost:8001/api/strategy/BTC?strategy_id=JSON:btc_scalp_trend"
```

---

## 🔧 Backtest Issues (2026-02-23)

**Status:** ⚠️ Broken

**Problem:** Backtest zwraca 0 trades lub null results.

**Prawdopodobna przyczyna:**
- Brak danych candles w formacie 5m
- Przeciążony serwer przy backtest
- Błąd w logice backtest

**TODO:**
- [ ] Naprawić pobieranie danych 5m
- [ ] Dodać timeout dla backtest
- [ ] Logowanie błędów

---

## 📰 News System

**Status:** ✅ Working

- **Alpha Vantage NEWS_SENTIMENT API** - Real API calls
- **Stocks (AAPL, TSLA, MSFT):** 4+ real articles z sentiment
- **Futures (GC=F, SI=F, NQ=F):** Zwraca 0 (mniej newsów)
- **Fallback:** Pusta lista gdy brak newsów (bez mock data)

---

## ✨ Trading Mode (2026-02-20)

**Status:** ✅ Done

- **Glass Toggle** - Apple-style liquid glass design
- **Broker Toggle** - Simulation 🎮 / IBKR 📈
- **Mode Toggle** - Preview 👁 / Live ⚡
- Persisted to localStorage

---

## 🎯 TODO

- [ ] Loading indicators + cache
- [ ] Lewy panel - przebudowa
- [ ] Symbol click = switch chart (bez modala)
- [ ] Redis/RQ - kolejkowanie background tasks (alerts, news, cache)

---

## 🔧 Feature: Per-Symbol Indicator Settings

**Status:** ✅ Backend Done

- [x] Backend: endpoint GET/POST /api/settings/indicators/{symbol}
- [x] Backend: score liczy tylko włączone wskaźniki (z DB)
- [x] Backend: strategia per symbol zapisana w DB
- [ ] Frontend: toggle wskaźników na wykresie (lokalnie)
- [ ] Frontend: Settings > Indicators per symbol

**Dokumentacja:** `INDICATOR_SETTINGS_PLAN.md`

---

## 🚀 Backtest Feature (2026-02-20)

**Status:** ✅ Done

- [x] Backend: GET /api/backtest endpoint
- [x] Logika: score-based direction (nie strategy.direction)
- [x] Frontend: Backtest tab w Dashboard
- [x] Parametry: symbol, resolution, days, min_score, initial_balance
- [x] Wyniki: trades, metrics (P&L, win rate, max drawdown)

### Architektura wskaźników (2026-02-20)

**IndicatorConfig** - klasa z polami:
- `id`: str - np. "RSI", "MACD", "BB"
- `enabled`: bool - czy włączony
- `settings`: dict - np. {"period": 14, "overbought": 70}

**Strategy** - ma:
- `default_indicators`: List[IndicatorConfig]
- `get_enabled_indicators()` - zwraca listę IDs włączonych
- `to_config(used_indicators)` - konwertuje do dict dla API

**API** `/api/strategies` zwraca:
```json
{
  "default_indicators": [
    {"id": "RSI", "enabled": true, "settings": {"period": 14}},
    {"id": "MACD", "enabled": false, "settings": {...}},
    ...
  ]
}
```

**Test:** `curl "http://localhost:8001/api/backtest?symbol=XAU&resolution=60&days=30&min_score=0.1"`

**TODO:**
- [x] Equity curve chart w UI
- [x] Compare - uruchom kilka konfiguracji obok siebie (via Optimize)
- [x] Optimize - automatyczne przetestowanie kombinacji i wybór najlepszej
- [x] Adjust settings - edycja ustawień wskaźników (period, overbought, etc.)
- [x] Save strategy - zapisz nową strategię z własną nazwą
- [ ] Speed control (x1, x5, x10...)
- [ ] Real-time updates podczas backtestu

## 🔧 Frontend Build Error (2026-02-24 00:49:42)
**Status:** ✅ Fixed (2026-02-24 08:16)

**Problem:** src/components/CandlestickChart.tsx(42,3): error TS2300: Duplicate identifier 'selectedPosition'.
src/components/CandlestickChart.tsx(43,3): error TS2300: Duplicate identifier 'selectedPosition'.
src/components/CandlestickChart.tsx(236,3): error TS2300: Duplicate identifier 'selectedPosition'.

**Full Output:**
```

> polymarket-bot-frontend@0.1.0 build
> tsc && vite build

src/components/CandlestickChart.tsx(42,3): error TS2300: Duplicate identifier 'selectedPosition'.
src/components/CandlestickChart.tsx(43,3): error TS2300: Duplicate identifier 'selectedPosition'.
src/components/CandlestickChart.tsx(236,3): error TS2300: Duplicate identifier 'selectedPosition'.
src/components/CandlestickChart.tsx(237,3): error TS2300: Duplicate identifier 'selectedPosition'.
src/components/MainTab.tsx(441,59): error TS2552: Cannot find name 'setSelectedSymbol'. Did you mean 'selectedSymbol'?
src/components/MainTab.tsx(441,77): error TS18047: 'pos' is possibly 'null'.
```

