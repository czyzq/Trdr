# Trading Optimization - Continuous Improvement

## Status: AKTYWNE

### Cron Job Setup
```bash
# Add to crontab (crontab -e)
*/30 * * * * /Users/pinchr/dev/cfd-trading-bot/run_optimization.sh >> /tmp/optimization_cron.log 2>&1
```

### Test Configurations (do przetestowania)

#### Batch 1: Simple Momentum variations
| # | Strategy | min_score | leverage | TP% | SL% | Trail% |
|---|----------|-----------|-----------|-----|-----|---------|
| 1 | simple_momentum | 0.01 | 3 | 4% | 2% | 0 |
| 2 | simple_momentum | 0.01 | 3 | 3% | 1.5% | 0 |
| 3 | simple_momentum | 0.01 | 3 | 5% | 2.5% | 0 |
| 4 | simple_momentum | 0.01 | 3 | 4% | 2% | 1% |
| 5 | simple_momentum | 0.01 | 3 | 4% | 2% | 1.5% |

#### Batch 2: Adaptive Regime
| # | Strategy | min_score | leverage | TP% | SL% |
|---|----------|-----------|-----------|-----|-----|
| 6 | adaptive_regime | 0.01 | 3 | 4% | 2% |
| 7 | adaptive_regime | 0.05 | 3 | 4% | 2% |
| 8 | adaptive_regime | 0.01 | 5 | 4% | 2% |

#### Batch 3: MMS
| # | Strategy | min_score | leverage | TP% | SL% |
|---|----------|-----------|-----------|-----|-----|
| 9 | mms | 0.01 | 3 | 3% | 2% |
| 10 | mms | 0.01 | 2 | 3% | 2% |

### Najlepsze wyniki (2026-02-21)

**🏆 BEST FOUND (2026-02-21 - Parallel Research):**

| Rank | Strategy | Resolution | Lev | TP% | SL% | PnL | Win% |
|------|----------|------------|-----|-----|-----|-----|------|
| 1 | adaptive_regime | 30min | 10 | 3.5% | 2% | **$57.00** | **59.3%** |
| 2 | adaptive_regime | 30min | 15 | 3.5% | 2% | $85.56 | 59.3% |
| 3 | adaptive_regime | 30min | 20 | 3.5% | 2% | $114.16 | 59.3% |
| 4 | adaptive_regime | 15min | 10 | 3% | 2% | $82.30 | 62.1% |
| 5 | BTC | 15min | 10 | 3.5% | 2% | $47.68 | 44.4% |

**Key Discoveries:**
- **Resolution 30 min > 15 min** - better win rate (59% vs 62% but higher PnL on 30m)
- **TP=3.5%, SL=2%** - best risk/reward (59% win, good PnL)
- **XAU is best** - XAG and US100 are NOT profitable
- **BTC works too** - 2nd best symbol
- **Trailing SL hurts** - don't use it
- **min_score doesn't matter** - 0.005 to 0.03 gives same results

### Config: adaptive_regime_XAU (v30)

**Best config for XAU from backtest 2026-02-21**

| Parametr | Wartość |
|----------|---------|
| Symbol | XAU |
| Strategy | adaptive_regime |
| Resolution | 30 min |
| Leverage | 10 |
| TP | 3.5% |
| SL | 2% |
| min_score | 0.01 |

**Results:** $57.00, 59.3% win rate (30 days backtest)

**Status:** 
- ✅ Leverage set to 10 for XAU
- ⚠️ Auto-trade currently uses ATR-based TP/SL (3x/2x ATR), not %-based
- ⚠️ Resolution not used in live trading (only for signal generation frequency)

**Next steps to enable %-based TP/SL:**
- Modify auto_trade_loop to use tp_pct/sl_pct instead of ATR
- Set resolution in signal generation (currently defaults to 60)

---

## Symbol Trading Toggles (2026-02-21)

| Symbol | Trading Enabled |
|--------|-----------------|
| XAU | ✅ ON |
| XAG | ❌ OFF |
| US100 | ❌ OFF |
| BTC | ❌ OFF |

**Settings in DB:** 
- `TRADE_ENABLED_{SYMBOL}` (1 = enabled, 0 = disabled)
- `DYNAMIC_RISK_ENABLED` (1 = on, 0 = off)

### Dynamic Risk System
| Open Positions | Risk per Trade | Total Risk |
|---------------|----------------|------------|
| 1 | 2.0% | 2.0% |
| 2 | 1.0% | 2.0% |
| 3 | 0.67% | 2.0% |

**Minimum risk per trade:** 0.5% (won't go lower even with many positions)

---

## Multi-Symbol Backtest Results (2026-02-21)

### Best Config Found: XAU + BTC

| Symbols | Resolution | Leverage | TP% | SL% | 30-day PnL |
|---------|------------|----------|-----|-----|------------|
| XAU + BTC | 15min | 15 | 3% / 3.5% | 2% | **$196.32** |
| XAU + BTC | 15min | 20 | 3% / 3.5% | 2% | $262.39 |
| XAU + BTC | 15min | 25 | 3% / 3.5% | 2% | $328.76 |
| XAU + BTC + US100 | 15min | 15 | 3% | 2% | $198.91 |

### Key Findings:
- **XAU + BTC is optimal** - adding US100 only adds ~$2
- **XAG is NOT profitable** - loses money, keep disabled
- **Higher leverage = more profit** (linear)
- **15min resolution > 30min** for this combo

### Recommended Settings:
- XAU: ON, Lev=15, TP=3%, SL=2%
- BTC: ON, Lev=15, TP=3.5%, SL=2%
- XAG: OFF
- US100: OFF (or ON for small diversification)

### Co testować dalej
- [ ] Volume filter (0.5, 0.7, 1.0)
- [ ] Different symbols (BTC, XAG, US100)
- [ ] Different resolutions (5m, 30m)
- [ ] Trailing SL z różnymi wartościami

### Automatyzacja
- [x] Skrypt: run_optimization.sh
- [ ] Cron: co 30 minut
- [ ] API: /api/backtest/batch (do dodania)

### Notatki
- Dane z Binance działają poprawnie
- Simple Momentum generuje więcej trades ale mniej zysku
- Adaptive Regime ma lepszy win rate
- Problem: niskie min_score = więcej trades = większe ryzyko

## Volume Filter Bug Fix (2026-02-21)
- Bug: `avg_volume` was used but never defined
- Fix: Calculate avg from last 20 candles before filtering
- Status: ✅ Fixed and working!

---

## 🎯 FINAL CONFIG (2026-02-21)

### BTC Configuration:
| Parameter | Value |
|-----------|-------|
| Symbol | BTC |
| Resolution | 15 min |
| min_score | 0.005 |
| Leverage | 20 |
| TP | 5% |
| SL | 2% |
| Volume Filter | 0.45 |

### Results:
- Expected: ~$268/month (8.9% return)
- 58% win rate
- 26 trades/month

### Status:
- ✅ Server running on port 8001
- ✅ Auto-trade enabled
- ✅ BTC trading enabled
- ✅ XAU, XAG, US100 disabled
- ⚠️ Balance: $3094.32 (lost ~$128 from previous session)

---

## Strategy: STRATEGY_BTC_V2 (2026-02-22) - Simplified Core

### Config:
- **Symbol**: BTC
- **Resolution**: 15 min (test also 5m)
- **min_score**: 0.005 (5m: 0.01-0.015)
- **Leverage**: 20
- **TP**: 5%
- **SL**: 2%
- **Volume Filter**: 0.45

### Core (KEEP):
✅ Weighted score (RSI/MACD/Momentum)
✅ Volume filter
✅ 2% total risk
✅ Fixed SL/TP
✅ Dynamic TP via RSI_HTF

### Removed (NOT WORKING):
❌ Divergence
❌ Order Block
❌ HTF ADX/VWAP
❌ Multi-TF alignment

### New HTF Filter (v2):
- Simple trend filter: RSI_30m > 50 = long only, < 50 = short only
- Soft filter: adjust min_score instead of blocking

### TODO:
- [ ] Test 5m with min_score=0.01
- [ ] Test 5m with 2/3 indicators agreement
- [ ] Clean backtest on 90+ days
- [ ] Test on XAU, XAG, US100

---

## STRATEGY_BTC_V2 (2026-02-22)

### Config:
- Symbol: BTC
- Resolution: 5 min
- min_score: 0.01
- Leverage: 50
- TP: 5%
- SL: 2%
- Volume Filter: 0.45

### Results:
- Trades: 45/month
- PnL: $335/month (~11%)
- Win Rate: 58%

---

## STRATEGY_BTC_V3 (PLANNED)

### 1. Score Weights:
- MACD: 0.35
- RSI: 0.35
- Momentum: 0.2
- ADX: as filter only (not in score)

### 2. ADX Filter:
- ADX > 25 = trending → TP=5%
- ADX < 20 = chop → TP=3%, SL=1.5%

### 3. ATR-based SL/TP

### 4. Volume Tiers:
- < 0.45× = skip
- 0.45-1.0× = normal  
- > 1.5× = boost

### 5. Risk Engine:
- Max exposure: notional ≤ 100% balance
- Daily DD limit: stop if -5%

### 6. Time Filters:
- Max trades/day
- Stop after 3 SL in a row
