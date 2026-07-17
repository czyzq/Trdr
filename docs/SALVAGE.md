# SALVAGE — reusable ideas mined from dead files before overhaul deletion

Origin cited per item. All backtest numbers are from the old inline backtester (no spread/fees, see Cost-model notes) — treat as priors, not truth.

## HTF/MTF filter rules (pseudocode per filter)

All from `backend/main.py` inline backtester (~lines 660-1190). Common mechanics: each filter takes a resolution string (e.g. `"30"`, `"60"`), loads that TF's candles from Mongo, and at each base-TF candle finds the first HTF candle with `timestamp >= current_ts` (index `j`), then computes on the window *before* `j`. Only the `htf_trend` filter explicitly uses the previous CLOSED candle (`j-1`) to avoid look-ahead; the others implicitly use `[.., j)` windows. All are entry vetoes applied after `score >= min_score` produced a candidate direction.

### htf_rsi (extreme veto)
```
rsi = RSI14 over last 14 HTF closes before current ts   # simple avg gain/loss, not Wilder
if direction == buy  and rsi > 70: SKIP
if direction == sell and rsi < 30: SKIP
```
Also used in-trade for dynamic TP (only while position open):
```
buy:  rsi > 65 -> tp_pct = min(tp_pct, 3%);  rsi < 40 -> tp_pct = max(tp_pct, 6%)
sell: rsi < 35 -> tp_pct = min(tp_pct, 3%);  rsi > 60 -> tp_pct = max(tp_pct, 6%)
```

### htf_adx (no-trend veto)
```
over last 14 HTF candles: +DM/-DM/TR the classic way (sums / 14)
atr = mean(TR); plus_di = sum(+DM)/14/atr*100; minus_di likewise
dx = |plus_di - minus_di| / (plus_di + minus_di) * 100
if dx < 20: SKIP (no trend)
```

### htf_resistance (TP compression near HTF extremes)
```
window = last 20 HTF candles; htf_high = max(high); htf_low = min(low); range = high-low
dist_to_high = (htf_high - price)/range;  dist_to_low = (price - htf_low)/range
buy  and dist_to_high < 0.10 -> tp_pct *= 0.7
sell and dist_to_low  < 0.10 -> tp_pct *= 0.7
```
Not a veto — reduces target when running into HTF structure.

### htf_vwap (right-side-of-VWAP veto)
```
vwap = sum(typical_price * vol) / sum(vol) over last 20 HTF candles  (typical = (H+L+C)/3)
buy:  require price > vwap, OR previous HTF close was already below its VWAP (crossing up)
sell: require price < vwap, OR previous HTF close was already above its VWAP (crossing down)
else SKIP
```

### htf_trend (SOFT filter — the only one that survived pruning)
```
htf_rsi = RSI14 on last CLOSED HTF candle (index j-1; no look-ahead)
buy  and htf_rsi < 45: require |score| >= 2 * min_score, else SKIP
sell and htf_rsi > 55: require |score| >= 2 * min_score, else SKIP
```
Soft = raises the score bar when trading against HTF trend instead of hard-blocking. OPTIMIZATION_TASKS.md v2 verdict: keep this one; drop the hard filters.

### multi_tf (agreement veto)
```
for each extra TF: direction = sign(close[j] - close[j-1]) at the candle nearest current ts
if any TF direction is non-null and != signal direction: SKIP
```
Naive (2-candle slope). If revived, use a real trend measure per TF.

### divergence_filter (RSI only implemented)
```
compare RSI and price vs previous candle:
buy  and price up   and rsi down (bearish divergence): SKIP
sell and price down and rsi up   (bullish divergence): SKIP
```

### order_block_filter
```
look back 5 candles for an "order block" (green candle for buys, red for sells)
buy:  price within [ob_high*0.99, ob_high*1.02] -> ok, else SKIP
sell: price within [ob_low*0.98,  ob_low*1.01]  -> ok, else SKIP
```
Buggy as written (only inspects first candle in loop, else-branch skips). Idea only.

### volume_filter
```
avg_volume = mean(volume of last 20 candles, ignoring 0/None)
if current_volume < avg_volume * threshold: SKIP    # threshold ~0.45-1.0
```
Empirically kept (0.45 best for BTC). V3 idea: tiers — <0.45x skip, 0.45-1.0x normal, >1.5x boost score.

## Empirical strategy findings (optimizer priors)

What worked / was removed (OPTIMIZATION_TASKS.md "STRATEGY_BTC_V2" section):
- KEEP: weighted score (RSI/MACD/Momentum), volume filter (0.45), 2% total risk, fixed SL/TP, dynamic TP via HTF RSI, soft HTF trend filter.
- REMOVED as not working: divergence filter, order-block filter, HTF ADX, HTF VWAP, multi-TF alignment (hard agreement).
- Trailing SL hurts — don't use (OPTIMIZATION_TASKS.md 2026-02-21).

Per-symbol / per-TF priors:
- BTC: best performer. btc_scalp_trend 60m ~+14.4%/30d (STRATEGY_CHANGES.md). Earlier: 15m TP 3.5%/SL 2%, and 5m min_score 0.01. BTC results "capped" at ~216 trades regardless of 7-60d period — smells like a data-window cap, verify candle coverage before trusting.
- XAU: low trade count is the limiter. xau_base (min_score 0.15) 41 trades +5.9% on 14-21d/60m beats every variant; lowering min_score to 0.75x → 126 trades, -17.9%. xau_v2/v3 momentum variants: -34.4%. XAU on 30d/60m degrades (278 trades, -17.1%) — period-sensitive.
- XAG: contradictory. 2026-02-21: "XAG is NOT profitable, keep disabled" (-$86/90d, 32% WR — OPTIMIZATION_PROGRESS.md). 2026-03-13: xag_v3_exp +20.0% on 21-45d/60m (STRATEGY_CHANGES.md). Highly config/period sensitive; treat as unstable, demand out-of-sample confirmation.
- US100: too few trades (~27/90d), marginal PnL. Adding it to XAU+BTC portfolio added ~$2 (OPTIMIZATION_PROGRESS.md, OPTIMIZATION_TASKS.md).
- Portfolio: XAU+BTC recommended; adding XAG dragged 4-symbol win rate from 56% to 44% (OPTIMIZATION_PROGRESS.md).
- min_score: mostly flat 0.005-0.03 for scoring strategies (OPTIMIZATION_TASKS.md); but for XAU it's the single most important knob (see above). Backtester once silently forced min_score=0.0 for "unified" strategies (STRATEGY_CHANGES.md 2026-03-13 01:23) — many scans were invalid; be suspicious of results from that era.
- Win rate is not the objective: btc_scalp_trend 40.7% WR +14.4% beat btc_base 47.5% WR -26.5% (STRATEGY_CHANGES.md).
- Resolution: 30m vs 15m flipped winner depending on symbol set; 60m was the final settled TF for all three symbols (STRATEGY_CHANGES.md).
- BACKTEST_RESULTS.md 2026-03-11 fixes that mattered: per-symbol min_score 0.30/0.28/0.20 → 0.05 multiplied trade counts; RSI 45-55 and StochRSI 20-80 neutral zones changed from "return 0" to weak directional score.
- Leverage vs IBKR reality (bugs.md #5, #8): max instrument leverage XAU=20, XAG=10, US100=20, BTC=2. Old backtests ran BTC at lev 20-50 — those PnLs are not achievable live. XAG contract multiplier is 5, not 100 (bugs.md #4).
- Dynamic risk split (OPTIMIZATION_TASKS.md): total risk fixed 2%, divided across open positions (1 pos→2%, 2→1%, 3→0.67%), floor 0.5%/trade.
- V3 planned-but-untested ideas worth carrying: ADX regime switch (ADX>25 → TP 5%; ADX<20 → TP 3%/SL 1.5%), ATR-based SL/TP, max notional ≤ 100% balance, daily drawdown stop at -5%, max trades/day, stop after 3 consecutive SL.
- Time stop in old backtester: force-close after 240 base candles (intended "4h" — only true on 1m; on 60m it's 10 days; decide time stops in wall-clock, not candles).
- Adaptive TP/SL blend spec (TEST_SCENARIOS_V1.md): base percent 30%, ATR multiplier 30%, support/resistance 20%, HTF indicator 20%.
- 5m/15m/240m candles were missing in Mongo for XAU/XAG — several "no improvement on other TF" conclusions were actually "no data" (STRATEGY_CHANGES.md).

## Cost-model notes

From DEBUG_SL_TP.md (open investigation, never closed):
- Spread is NOT accounted anywhere: entries should fill at ask, exits at bid. Add per-instrument spread to the new cost model — this alone likely erases the thin-edge configs above.
- P&L formula `(exit - entry) * size * leverage` is correct only if `size` is in units (oz/contracts) and leverage semantics are consistent; XAU 1 lot = 100 oz, size stored in lots. Pin down unit conventions once, centrally.
- 2% price SL at 20x leverage = 40% of margin — express SL both in price% and margin% in the new schema.
- Live loop checked SL/TP every 5s immediately after open → positions closed instantly on noise/spread. Recommendations: log actual SL/TP at open, small grace delay before first check, verify against chart price.
- Old backtester (main.py) checks TP/SL against CLOSE only, not high/low — underestimates SL hits and TP touches. framework.py has the same close-only check.
- framework.py PnL bug to not repeat: `size` already includes leverage (`balance*risk*lev/price`) and TP/SL PnL multiplies by leverage again (`size * entry * tp_pct * leverage`) — leverage applied twice; also PnL uses nominal tp_pct/sl_pct, not the actual exit price.
- Old backtester has no fees, no slippage, no overnight financing, no gap-through-SL modeling. New cost model should cover: spread, commission, swap/financing, slippage, and intrabar TP/SL ambiguity (which side hit first).

## News & data source notes

From NIGHT_RESEARCH.md (2026-02-20 findings):
- X/Twitter API: pay-per-use only, no free tier — dead end for scraping. Nitter instances down/blocked, RSS via Nitter dead.
- Yahoo Finance RSS feeds broken; direct page scraping works.
- NewsAPI.org: free tier 100 req/day, `https://newsapi.org/v2/everything?q=gold+OR+xau`, registration required. Never actually tried.
- Untested candidates: Finviz RSS, CryptoPanic API, StockTwits API, TradingView community signals.

From backend/finnhub.py:
- Finnhub endpoints used: `GET /quote`, `GET /forex/candle` (resolutions 1/5/15/30/60/D/W/M), `GET /company-news`. Token as `token` query param.

From backend/news_client.py (Brave Search):
- Endpoint `https://api.search.brave.com/res/v1/web/search`, header `X-Subscription-Token`, params `q`, `count`, `freshness=past-24h`.
- Rate limit constants that worked: 1 req/s min interval (free plan; comment says 20 req/min), 120s response cache, 3s HTTP timeout, on 429 return empty (don't retry).
- Symbol→query map: XAU→"gold price news", XAG→"silver price news", US100→"nasdaq nasdaq-100 news".
- Naive keyword sentiment: bullish/bearish keyword lists, score = (bull-bear)/total, direction thresholds ±0.2. Cheap baseline; replace with a real model but keep the interface (headline, sentiment, direction, importance, source, url, published).

From backend/web_scraping_news.py:
- Scrape targets and paths: investing.com `/commodities/gold-news`, `/commodities/silver-news`, `/indices/nasdaq-100-news`; MarketWatch search `/search?q={symbol} news`; Yahoo `/quote/{sym}/news`.
- Etiquette constants: 0.5s min delay between requests, 180s cache, 10s total timeout, desktop UA string. SSL verification was disabled — don't copy that.
- Multi-source cascade pattern (fill up to `limit` from source 1, then 2, then 3; sort by importance) is reusable.

## UI ideas

From ui_ideas/*.JPG (screenshots of other bots, inspiration):
- IMG_0336/0337 ("Polymarket Alpha Scanner", terminal aesthetic): live console log of the scan pipeline with per-filter funnel counts ("min_volume → 312 passed, min_liquidity → 189, edge_threshold → 47, structural_edge → 23"); left rail with System Status (engine state, connection dots per dependency, uptime, memory), Scan Config, Current Scan, and Performance (win rate, avg edge, total scans, 30d ROI); results as a ranked table (market, prob, volume, alpha score). The filter-funnel visualization maps directly onto a multi-TF veto chain — show how many candidate signals each veto killed.
- IMG_0340 ("Mahoraga v2" dashboard): equity + cash + buying power header; positions table with inline P&L sparklines per row; LLM cost panel (total spent, API calls, tokens in/out, avg cost/call, model name) — reuse if the overhaul calls an LLM; portfolio performance chart + per-position %-change multi-line chart.
- IMG_0338: the tweet the scanner came from — pipeline idea: scan all markets → rank by alpha → send top picks to deep research → auto confirm/reject thesis → wake up to executable list.
- IMG_0339: not UI — a CLAUDE.md "Workflow Orchestration" ruleset (plan mode default, subagent strategy, lessons.md self-improvement loop, verification before done). Keep as agent-workflow inspiration if desired.

From docs/FEATURE_POSITION_LINES.md: entry (solid) / TP / SL (dashed) horizontal lines across chart, colored by direction; drag-slider TP/SL editing with live preview line and explicit confirm modal (drag → "unconfirmed" → confirm → API). Slider ranges: TP entry±10%, SL entry±5%.

From docs/UI_IMPROVEMENT_PLAN.md (still-relevant bits): price "pill" background on Y axis; SL/TP text contrast (was unreadable dark-gray-on-black); position card progress bar as red→gray→green gradient showing price position between SL and TP; PROFIT/LOSS badges; drawdown alert box when DD > 5%; win-rate donut; position duration ("1h 24m") on cards. Known chart bugs if old chart code is reused: trade markers offset by BB warmup index; indicator arrays shorter than candle array (truncated lines).

From SIGNAL_FILTER_FIX.md: signals table should filter to the chart-selected symbol (sync selection state down; show all when none selected).

From BACKTEST_PLAN.md: backtest as a third UI mode next to Preview/Live; config panel (symbol, TF, date range, initial balance) + replay speed slider (x1-x50) with pause; results = equity curve + trades table + metrics (PnL, win rate, max DD, Sharpe, count).

From INDICATOR_SETTINGS_PLAN.md: two-layer indicator toggles — chart-local visual toggle (localStorage, no backend effect) vs Settings per-symbol config persisted to DB that actually changes score computation. Good separation to keep.

## Still-open issues worth tracking

- Spread/fee accounting absent end-to-end (DEBUG_SL_TP.md) — the whole recommendations list there was never executed: log SL/TP at open, delay first price check, per-symbol decimals in edit inputs, verify CFD contract specs in P&L.
- `original_signal_score = 0.0` on opened positions broke Dynamic Positions signal-decay exits (TEST_SCENARIOS.md B2 FAIL). TEST_SCENARIOS_V1.md marks a fix ✅ but it was never re-verified end-to-end (B3 "not tested").
- Dynamic TP (HTF RSI rules from strategy JSON) works in code but has zero visibility in API/signal payloads — can't audit what TP was actually applied (TEST_SCENARIOS.md A2).
- Backtester forced `min_score=0.0` for unified strategies (STRATEGY_CHANGES.md) — if any of that code survives, fix before trusting scans.
- `asyncio.sleep(300)` inside a uvicorn task silently never wakes; chunked 60s sleeps fixed it (docs/AUTO_TRADE_LOOP_FIX.md). Keep the chunked-sleep (or move loops out-of-process) in the new architecture.
- Dual signal paths (new JSON ScoreEngine vs legacy `calculate_signal_score`) with different normalization — FIXES.md Issue 3 recommendation to standardize on JSON strategies was never completed.
- Missing 5m/15m historical data for XAU/XAG in Mongo blocked lower-TF optimization (STRATEGY_CHANGES.md).
- No automatic support/resistance detection; TP/SL purely %-based (TEST_SCENARIOS.md A4).

## Misc

- A/B framework semantics (backend/backtest/framework.py): its one good idea is **live-parity** — the backtest imports and calls the same `calculate_adaptive_tp_sl` and `calculate_dynamic_position_size` used by live trading, so config changes are tested through the real code path. A/B = run same engine twice with config A/B on same candles, winner by total_pnl, persisted as one doc `{result_a, result_b, comparison: {winner, pnl_difference, win_rate_difference}}` in `backtest_results`. Report fields worth keeping: avg_score/avg_confidence per run, exit_type per trade (TP/SL/trailing/time), candles_used, execution_time.
- Self-optimizing loop spec (AUTO_BACKTEST_OPTIMIZER.md) — best salvage for the new optimizer: 10-min cycle tests 5 least-recently-tested combos; hourly cycle aggregates, compares vs per-symbol "best strategy" baseline, promotes winners, persists best configs; dynamic lookback scaled to ~1000-2000 candles per TF (5m→1wk, 15m/30m→2wk, 1H→1mo, 4H→3mo, 1D→1yr); result schema includes profit_factor, avg_trade_pct, max_drawdown and a free-text `parameter_impact` insight; insights log is re-read at startup to steer the next search (avoid re-testing near-known-losers, continue improving directions).
- Strategy-as-source-of-truth (FIXES.md Issue 2): filters (volatility max_atr_percent, VIX max) belong in strategy JSON and a FilterChain, never hardcoded in the orchestrator. Carry this principle into the new veto/filter schema.
- Momentum sign inversion (FIXES.md Issue 1): rsi_momentum strategies traded REVERSED for a period (positive momentum → sell). Any historical results from btc/xau/xag_v3_exp before 2026-03-04 are contaminated.
- Strategy JSON schema sketches worth reusing (TEST_SCENARIOS.md): `exits.{stop_loss,take_profit}.type: percent_from_entry|atr_multiplier|price_level`, `dynamic_tp.rules[{condition:{operator,value}, tp_percent}]` on an HTF indicator, and `risk.{risk_per_trade_pct, max_total_risk_pct, leverage, max_notional_exposure_multiple}` with explicit sizing formula + rounding step.
- Fixed walk-forward windows idea (backtest_schedule.md): identical 4 x 7-day weeks for all symbols, TF-dependent window length — crude but a seed for proper walk-forward splits.
- Backtest determinism gotcha (TEST_PROGRESS.md 2026-03-03): stateful incremental indicators kept state between runs → non-deterministic results until `force_reload=True` reset them. New engine should construct fresh indicator state per run by design. Same log: MACD buffer must be sized by slow period (26), not signal period (9).
