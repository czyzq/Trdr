"""Gate tests for the unified backtester: determinism, known-answer fills/costs,
metrics math, and live==backtest parity. The optimizer must not ship unless
these pass — otherwise it optimizes a simulator that doesn't match the bot.
"""

import math
from datetime import datetime, timedelta

import pytest

from backtest.costs import CostModel, InstrumentCosts
from backtest.engine import run_backtest
from backtest.metrics import BacktestReport, TradeRecord, bars_per_year
from services.candle_store import CandleSeries
from strategy.engine import MarketSnapshot, SignalEngine
from timeframes import TimeFrame


def _candles(n, tf_min, end=None, drift=0.3, base=100.0):
    end = end or datetime(2026, 1, 10, 12, 0, 0)
    out, price = [], base
    for i in range(n):
        ts = end - timedelta(minutes=tf_min * (n - i))
        prev = price
        price *= 1 + drift / 100
        w = math.sin(i * 0.9) * base * 0.002
        c = price + w
        out.append({"timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                    "open": prev, "high": max(prev, c) + abs(w),
                    "low": min(prev, c) - abs(w), "close": c, "volume": 100 + i})
    return out


CFG = {
    "id": "gate", "symbol": "BTC", "base_timeframe": "5m",
    "timeframes": {"5m": {"weight": 1.0, "indicators": [
        {"name": "MOMENTUM", "weight": 1.0}, {"name": "RSI", "weight": 1.0}]}},
    "combine": {"min_score": 0.05, "min_agreement": 0.0, "conflict_policy": "ignore"},
    "risk": {"risk_per_trade_percent": 1.5, "leverage": 2},
    "exits": {"stop_loss": {"value": -2.0}, "take_profit": {"value": 4.0}},
}


# ── determinism ──


def test_backtest_deterministic_trade_hash():
    data = {"5m": _candles(800, 5)}
    r1 = run_backtest(CFG, data, initial_balance=3000.0)
    r2 = run_backtest(CFG, data, initial_balance=3000.0)
    h1 = hash(tuple((t.entry_ts, t.exit_ts, t.net_pnl_usd) for t in r1.trades))
    h2 = hash(tuple((t.entry_ts, t.exit_ts, t.net_pnl_usd) for t in r2.trades))
    assert h1 == h2
    assert r1.equity_curve == r2.equity_curve


def test_two_engines_interleaved_do_not_share_state():
    data_a = {"5m": _candles(600, 5, drift=0.3)}
    data_b = {"5m": _candles(600, 5, drift=-0.3)}
    solo_a = run_backtest(CFG, data_a)
    solo_b = run_backtest(CFG, data_b)
    again_a = run_backtest(CFG, data_a)  # after B ran
    assert [t.net_pnl_usd for t in solo_a.trades] == [t.net_pnl_usd for t in again_a.trades]
    assert solo_a.metrics != solo_b.metrics


# ── known-answer: fills & costs ──


def _costs():
    return CostModel("XAU", InstrumentCosts(spread_abs=0.4, slippage_bps=10.0,
                                            swap_long_bps=-10.0, swap_short_bps=-5.0))


def test_entry_pays_half_spread():
    cm = _costs()
    assert cm.entry_fill(2000.0, "buy") == pytest.approx(2000.2)
    assert cm.entry_fill(2000.0, "sell") == pytest.approx(1999.8)


def test_gap_through_stop_fills_at_open():
    cm = _costs()
    hs = cm.half_spread(1990.0)  # stops cross the spread like any market exit
    # long SL at 1990, bar opens at 1980 (gapped through) -> fill from the open,
    # minus half-spread and slippage
    fill = cm.stop_fill(1990.0, 1980.0, "buy")
    assert fill == pytest.approx((1980.0 - hs) * (1 - 10 / 10_000))
    # no gap: bar opens above the stop -> fill at the stop level (spread+slippage adjusted)
    fill2 = cm.stop_fill(1990.0, 2000.0, "buy")
    assert fill2 == pytest.approx((1990.0 - hs) * (1 - 10 / 10_000))


def test_swap_nights_triple_wednesday_and_weekend():
    cm = _costs()  # non-crypto: weekdays only, Wednesday x3
    opened = datetime(2026, 1, 5, 10, 0)   # Monday
    closed = datetime(2026, 1, 9, 10, 0)   # Friday
    # rollovers: Mon 21:00, Tue, Wed(x3), Thu -> 1+1+3+1 = 6
    assert cm.swap_nights(opened, closed) == 6
    btc = CostModel("BTC")
    # crypto: every night counts
    assert btc.swap_nights(datetime(2026, 1, 9, 10, 0), datetime(2026, 1, 12, 10, 0)) == 3


def test_swap_cost_sign_and_magnitude():
    cm = _costs()
    opened = datetime(2026, 1, 5, 10, 0)
    closed = datetime(2026, 1, 6, 10, 0)   # one rollover (Mon 21:00)
    cost = cm.swap_cost(10_000.0, "buy", opened, closed)
    assert cost == pytest.approx(10_000 * -10 / 10_000)  # -10 USD


def test_net_gross_costs_identity():
    """gross = mid-to-mid P&L, net = fill-to-fill + swap, and net == gross - costs."""
    data = {"5m": _candles(800, 5)}
    report = run_backtest(CFG, data, initial_balance=3000.0)
    assert len(report.trades) > 0
    for t in report.trades:
        # identity holds by construction
        assert t.net_pnl_usd == pytest.approx(t.gross_pnl_usd - t.costs_usd, abs=0.03)
        # fill-to-fill P&L plus financing is what the account actually gained
        fill_pnl = (t.exit_price - t.entry_price) * t.size if t.direction == "buy" \
            else (t.entry_price - t.exit_price) * t.size
        assert abs(t.net_pnl_usd - fill_pnl) < max(abs(fill_pnl) * 0.05 + 1.0, 5.0)  # swap-sized gap only
    assert report.final_balance == pytest.approx(
        report.initial_balance + sum(t.net_pnl_usd for t in report.trades), abs=0.5)


def test_costs_reduce_pnl_vs_zero_cost():
    data = {"5m": _candles(800, 5)}
    free = CostModel("BTC", InstrumentCosts(spread_abs=0.0, slippage_bps=0.0,
                                            swap_long_bps=0.0, swap_short_bps=0.0))
    r_free = run_backtest(CFG, data, cost_model=free)
    r_real = run_backtest(CFG, data)
    assert r_real.metrics["net_pnl_usd"] < r_free.metrics["net_pnl_usd"]


# ── metrics math ──


def test_bars_per_year_table():
    assert bars_per_year(5, "BTC") == pytest.approx(24 * 12 * 7 * 52)
    assert bars_per_year(60, "XAU") == pytest.approx(23 * 5 * 52)


def test_sharpe_hand_computed():
    report = BacktestReport(symbol="BTC", strategy_id="x", timeframe="5m",
                            window_from="", window_to="", initial_balance=100.0,
                            final_balance=103.0)
    report.equity_curve = [100.0, 101.0, 100.5, 102.0, 103.0]
    report.trades = [TradeRecord("BTC", "buy", "", "", 1, 1, 1, 3.0, 0.0, 3.0, "tp", 4)]
    m = report.compute_metrics(5)
    rets = [0.01, -0.00495049504950495, 0.014925373134328358, 0.00980392156862745]
    mean = sum(rets) / 4
    std = math.sqrt(sum((r - mean) ** 2 for r in rets) / 3)
    expected = mean / std * math.sqrt(bars_per_year(5, "BTC"))
    assert m["sharpe"] == pytest.approx(expected, rel=1e-3)


def test_max_drawdown_mark_to_market():
    report = BacktestReport(symbol="BTC", strategy_id="x", timeframe="5m",
                            window_from="", window_to="", initial_balance=100.0,
                            final_balance=100.0)
    report.equity_curve = [100.0, 120.0, 90.0, 110.0]
    m = report.compute_metrics(5)
    assert m["max_dd_pct"] == pytest.approx(25.0)  # 120 -> 90
    assert m["max_dd_usd"] == pytest.approx(30.0)


def test_objective_gates_on_trade_count():
    report = BacktestReport(symbol="BTC", strategy_id="x", timeframe="5m",
                            window_from="", window_to="", initial_balance=100.0,
                            final_balance=200.0)
    report.metrics = {"trades": 3, "net_pnl_usd": 100.0, "max_dd_usd": 5.0}
    assert report.objective(min_trades=10) == -float("inf")
    report.metrics["trades"] = 30
    assert report.objective(min_trades=10) == pytest.approx(100.0 - 2.0 * 5.0)


# ── parity: live wrapper vs engine ──


def test_live_wrapper_matches_engine_evaluation():
    """analyze_with_new_strategy must return exactly what SignalEngine computes."""
    import services.strategy_manager as sm

    candles = _candles(200, 5)
    series = {TimeFrame.M5: CandleSeries("BTC", TimeFrame.M5, candles)}
    price = candles[-1]["close"]

    engine = SignalEngine(CFG)
    snapshot = MarketSnapshot(symbol="BTC", ts=datetime(2026, 1, 10, 12, 0), price=price, series=series)
    direct = engine.evaluate(snapshot)

    class _FakeStrategy:
        config = CFG
        id = "gate"
        symbol = "BTC"

        class filters:
            @staticmethod
            def check_all(candle, symbol, direction, atr_percent=None, vix_value=None):
                return True, []

    class _FakeManager:
        strategies = {"gate": _FakeStrategy()}

        def get_enabled_strategies(self):
            return [self.strategies["gate"]]

    orig = sm.get_strategy_manager
    sm.get_strategy_manager = lambda *a, **k: _FakeManager()
    try:
        result = sm.analyze_with_new_strategy("BTC", candles, price,
                                              requested_strategy="JSON:gate", series=series)
    finally:
        sm.get_strategy_manager = orig

    if direct.direction == "neutral":
        assert result is None
    else:
        assert result is not None
        assert result["direction"] == direct.direction
        assert result["score"] == pytest.approx(direct.score)
        assert result["confidence"] == pytest.approx(direct.confidence)
        assert result["agreement"] == pytest.approx(direct.agreement)
