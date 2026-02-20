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

---

## 🔧 Feature: Per-Symbol Indicator Settings (branch: feature/per-symbol-indicator-settings)

**Status:** 📋 Planned

- [ ] Backend: endpoint do zarządzania wskaźnikami per symbol
- [ ] Backend: calculate_signal_score() czyta z DB
- [ ] Frontend: toggle wskaźników na wykresie (lokalnie)
- [ ] Frontend: Settings > Indicators per symbol
- [ ] Połączyć z API

**Dokumentacja:** `INDICATOR_SETTINGS_PLAN.md`
