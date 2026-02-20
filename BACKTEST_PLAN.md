# Backtesting Feature - Detailed Plan

## 1. Per-Symbol Indicator Settings

### Backend
- [ ] DB: settings collection dla wskaźników per symbol
- [ ] Endpoint `GET/POST /api/settings/indicators/{symbol}` - pobierz/zapisz wskaźniki
- [ ] Default wskaźniki: RSI, MACD, BB, SMA, ADX, Stochastic, Momentum
- [ ] Funkcja `calculate_score()` czyta z DB które wskaźniki używać

### Frontend
- [ ] Settings > Indicators - toggle włącz/wyłącz per symbol
- [ ] Zapis do API

---

## 2. Backtest Mode (Simulation Only)

### Backend
- [ ] Endpoint `POST /api/backtest/run`
- [ ] Parametry:
  - `symbol`: string (XAU, XAG, US100, BTC)
  - `resolution`: string (1, 5, 15, 30, 60, D)
  - `from_date`: string (YYYY-MM-DD)
  - `to_date`: string (YYYY-MM-DD)
  - `initial_balance`: float (default: 3000)
  - `indicators`: array (opcjonalne - użyj jeśli podane)
  - `min_score`: float (opcjonalne)
- [ ] Logika:
  1. Pobierz candles z zakresu dat
  2. Dla każdej świecy: oblicz wskaźniki, generuj sygnał
  3. Jeśli sygnał i spełnione warunki → otwórz pozycję
  4. Symuluj SL/TP/close → zapisz trade
  5. Zwróć wszystkie trades + metrics

### Frontend
- [ ] Sidebar: "Backtest" jako trzeci tryb (obok Preview/Live)
- [ ] Po wybraniu Backtest - pokaż panel konfiguracji:
  - **Symbol**: dropdown (XAU, XAG, US100, BTC)
  - **Interwał**: dropdown (1m, 5m, 15m, 30m, 1H, D1)
  - **Od**: date picker
  - **Do**: date picker (domyślnie dzisiaj)
  - **Initial Balance**: input (domyślnie 3000)
  - **Speed**: slider (x1, x5, x10, x25, x50)
- [ ] Przycisk "Start Backtest"
- [ ] Wyniki:
  - Equity curve chart (liniowy)
  - Trades table (symbol, direction, entry, exit, P&L)
  - Metrics: Total P&L, Win Rate, Max Drawdown, Sharpe, Trades Count

---

## 3. Speed Control (Frontend only)

- [ ] Slider x1, x5, x10, x25, x50
- [ ] Obliczenia:
  - x1 = 1 świeca / sekunda
  - x5 = 5 świec / sekunda
  - itd.
- [ ]实时 updating chart podczas backtestu
- [ ] Możliwość pauzy/zatrzymania

---

## 4. API Endpoints

```
GET    /api/settings/indicators/{symbol}
POST   /api/settings/indicators/{symbol}
        Body: { "indicators": ["RSI", "MACD", "BB", ...] }

POST   /api/backtest/run
        Query: ?symbol=XAU&resolution=5&from=2026-01-01&to=2026-02-20&balance=3000&speed=10
        
Response: {
  "status": "running|completed",
  "trades": [...],
  "metrics": {
    "total_pnl": 250.50,
    "win_rate": 0.65,
    "max_drawdown": 0.12,
    "sharpe_ratio": 1.8,
    "trades_count": 24,
    "duration_seconds": 12.5
  },
  "equity_curve": [[timestamp, balance], ...]
}
```

---

## 5. Frontend Components

### New Files
- `src/components/BacktestPanel.tsx` - konfiguracja backtestu
- `src/components/BacktestResults.tsx` - wykresy i wyniki

### Modified Files
- `Sidebar.tsx` - dodaj tryb Backtest
- `Dashboard.tsx` - obsługa trybu backtest

---

## 6. Database Schema

```json
// settings collection
{
  "_id": "indicators_XAU",
  "symbol": "XAU",
  "indicators": ["RSI", "MACD", "BB", "SMA", "ADX", "STOCH", "MOMENTUM"],
  "updated_at": "2026-02-20T12:00:00Z"
}
```

---

## TODO List

### Backend
- [ ] Endpoint GET/POST /api/settings/indicators/{symbol}
- [ ] Modify calculate_score() to read from DB
- [ ] Endpoint POST /api/backtest/run
- [ ] Backtest engine logic

### Frontend
- [ ] Add Backtest mode toggle in Sidebar
- [ ] BacktestPanel component
- [ ] Date range pickers
- [ ] Speed slider
- [ ] Results view with equity curve
- [ ] Real-time updates during backtest

---

*Created: 2026-02-20*
*Updated: 2026-02-20 - Added detailed backtest mode*
