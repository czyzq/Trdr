# FIXES.md - CFD Trading Bot

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

**Test:** `curl "http://localhost:8000/api/backtest?symbol=XAU&resolution=60&days=30&min_score=0.1"`

**TODO:**
- [ ] Equity curve chart w UI
- [ ] Speed control (x1, x5, x10...)
- [ ] Real-time updates podczas backtestu
