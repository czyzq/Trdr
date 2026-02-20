# Feature: Per-Symbol Indicator Settings

## Cel
Dodać możliwość konfigurowania które wskaźniki są używane do generowania sygnałów per symbol.

## Architektura

### 1. Backend (API + DB)
```
/api/settings/indicators/{symbol}  GET/POST
- Zwraca/Ustawia które wskaźniki są włączone per symbol
- Przykład: { "XAU": ["BB", "MACD", "RSI"], "BTC": ["RSI", "MACD"] }

Signal generation czyta z DB i liczy score tylko z włączonych wskaźników
```

### 2. Frontend - Charts
- Kliknięcie wskaźnika na wykresie = toggle wizualny (on/off)
- NIE wpływa na backend
- Zapis w localStorage lub per-chart state

### 3. Frontend - Settings
- Oddzielna sekcja do konfiguracji per-symbol
- Zmiany zapisują się do DB
- Wpływają na obliczanie score w backendzie

## Git Branch
```
feature/per-symbol-indicator-settings
```

## TODO List

### Backend
- [ ] Dodać endpoint `/api/settings/indicators/{symbol}`
- [ ] Zmodyfikować `calculate_signal_score()` aby czytał z DB
- [ ] Dodać default indicators per symbol

### Frontend
- [ ] Dodać UI do toggle wskaźników na wykresie (działa lokalnie)
- [ ] Dodać stronę Settings > Indicators per symbol
- [ ] Połączyć z API

### Testing
- [ ] Sprawdzić że zmiana ustawień wpływa na score
- [ ] Sprawdzić że wykres pokazuje/ukrywa wskaźniki

## Wskaźniki do obsługi
- Bollinger Bands (BB)
- MACD
- RSI
- Stochastic
- Williams %R
- SMA/EMA
- ATR
- Volume

---

*Created: 2026-02-20*
