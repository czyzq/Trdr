# Backtest Results - 2026-03-11 (Po naprawach)

## Naprawy wprowadzone tego dnia

1. **min_score** w backtester.py: XAU 0.30→0.05, XAG 0.28→0.05, BTC 0.20→0.05
2. **strong_threshold** w get_direction(): 0.45→0.25
3. **RSI neutral zone (45-55)**: zwracało 0 → teraz daje słaby kierunek
4. **StochRSI neutral zone (20-80)**: zwracało 0 → teraz daje słaby kierunek

---

## WYNIKI (14 dni, 5m TF)

| Symbol | Trades | Win Rate | PnL | Zmiana vs przed |
|--------|--------|----------|-----|-----------------|
| **BTC** | 39 | 43.6% | **+$104.11** | ✅ +$105 |
| **XAU** | 19 | 42.1% | -$30.28 | ⚠️ -$35 |
| **XAG** | 63 | 42.9% | **+$182.58** | ✅ +$160 |

---

## Szczegóły

### BTC (14 dni)
- Initial: $3,000
- Final: $3,104.11
- Winning: 17 / 39
- Losing: 22 / 39

### XAU (14 dni)  
- Initial: $3,000
- Final: $2,969.72
- Winning: 8 / 19
- Losing: 11 / 19

### XAG (14 dni)
- Initial: $3,000
- Final: $3,182.58
- Winning: 27 / 63
- Losing: 36 / 63

---

## Wnioski

1. **Naprawa min_score** - drastycznie zwiększyła liczbę trades (13→39 BTC, 37→63 XAG)
2. **RSI/Stoch neutral zones** - teraz generują sygnały nawet w strefie 45-55
3. **XAG najlepszy** - +$182.58 przy 63 trades
4. **BTC dobry** - +$104.11 przy 39 trades
5. **XAU wymaga optymalizacji** - mniej trades niż przed naprawą

## TODO
- Zbadać dlaczego XAU ma mniej trades
- Dodać więcej wskaźników do XAU
- Przetestować dłuższy okres (30 dni)
