# Backtest Results - 2026-03-11 (Strategy Comparison - Updated)

## Test Setup
- **Period:** 7 days (Mar 4-10, 2026)
- **Initial Balance:** $3,000
- **Resolution:** 5m
- **Backend:** Running ✅
- **MongoDB:** Connected ✅

---

## WYNIKI

### BTC (Bitcoin) - 7d
| Strategia | Trades | Win Rate | PnL | Status |
|-----------|--------|----------|-----|--------|
| adaptive_regime | - | 57.1% | +$151.07 | ✅ BEST |
| btc_v2_core | - | 41.7% | +$8.05 | ✅ |
| btc_v2_safe | - | 41.7% | +$8.05 | ✅ |
| btc_v3_exp | - | 38.5% | +$0.17 | ⚠️ |
| btc_scalp_trend | - | - | N/A | ⚠️ No trades |

**Najlepsza BTC:** adaptive_regime (+$151.07, 57.1% WR)

### XAU (Gold) - 7d
| Strategia | Trades | Win Rate | PnL | Status |
|-----------|--------|----------|-----|--------|
| xau_v3_exp | - | 50.0% | +$7.67 | ✅ |
| adaptive_regime | - | 60.0% | -$5.28 | ⚠️ |
| xau_v2_momentum | - | 0.0% | -$18.29 | ❌ |
| xau_scalp_trend | - | - | N/A | ⚠️ No trades |

**Najlepsza XAU:** xau_v3_exp (+$7.67, 50% WR) - choć adaptive_regime ma wyższą WR (60%)

### XAG (Silver) - 7d
| Strategia | Trades | Win Rate | PnL | Status |
|-----------|--------|----------|-----|--------|
| adaptive_regime | - | 40.5% | +$23.67 | ✅ |
| xag_v3_exp | - | - | - | 🔴 BUG |

**Najlepsza XAG:** adaptive_regime (+$23.67, 40.5% WR)

---

## PODSUMOWANIE

| Symbol | Najlepsza Strategia | PnL | Win Rate |
|--------|---------------------|-----|----------|
| **BTC** | adaptive_regime | +$151.07 | 57.1% |
| **XAU** | xau_v3_exp | +$7.67 | 50.0% |
| **XAG** | adaptive_regime | +$23.67 | 40.5% |

---

## 🔍 ANALIZA

1. **BTC:** adaptive_regime ZDECYDOWANIE najlepszy! +$151 vs +$8 dla JSON strategii. Ogromna różnica.

2. **XAU:** xau_v3_exp działa dobrze (+$7.67, 50% WR). adaptive_regime ma wyższą WR (60%) ale na minusie.

3. **XAG:** xag_v3_exp nadal ma buga (JSONStrategyWrapper.to_config). Użyj adaptive_regime.

4. **Scalp strategies:** btc_scalp_trend i xau_scalp_trend nadal nie generują trades.

---

## REKOMENDACJE

1. ✅ **BTC:** Użyj adaptive_regime (daje +$151 vs +$8 dla v2_core)
2. ✅ **XAU:** Użyj xau_v3_exp (+$7.67, 50% WR) 
3. ✅ **XAG:** Użyj adaptive_regime (xag_v3_exp ma buga)
4. 🔧 **Scalp strategies:** Wymagają dalszego debugowania

---

## PORÓWNANIE: JSON vs Adaptive Regime

| Symbol | JSON (v2/v3) | adaptive_regime | Różnica |
|--------|--------------|-----------------|---------|
| BTC | +$8.05 | +$151.07 | +$143 (18x lepsze!) |
| XAU | +$7.67 | -$5.28 | JSON lepsze |
| XAG | BUG | +$23.67 | adaptive_regime działa |

**Wniosek:** adaptive_regime jest ZNACZĄCO lepszy dla BTC. Dla XAU JSON strategie wychodzą na plus.

---

## OPTIMIZACJA (na podstawie poprzednich wyników)

- ✅ Potwierdzono: adaptive_regime dla BTC - najlepsze wyniki
- ✅ Potwierdzono: xau_v3_exp dla XAU - działa
- 🔧 xag_v3_exp wymaga naprawy buga
- ⚠️ Indicator weights w JSON strategiach mogą być zbyt niskie (0.5)
