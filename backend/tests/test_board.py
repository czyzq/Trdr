"""Tests for the multi-timeframe indicator board (strategy/board.py)."""

import math
from datetime import datetime, timedelta

from services.candle_store import CandleSeries
from strategy.board import BOARD_INDICATORS, VOTE_THRESHOLD, compute_board
from timeframes import TimeFrame


def _candles(n, tf_minutes, end=None, trend=0.0, base=100.0):
    """Deterministic candle series; trend = per-bar % drift."""
    end = end or datetime(2026, 1, 10, 12, 0, 0)
    out = []
    price = base
    for i in range(n):
        ts = end - timedelta(minutes=tf_minutes * (n - i))
        prev = price
        price = price * (1 + trend / 100)
        # small deterministic wiggle so indicators are non-degenerate
        wiggle = math.sin(i * 0.7) * base * 0.001
        close = price + wiggle
        out.append({
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S"),
            "open": prev,
            "high": max(prev, close) + abs(wiggle),
            "low": min(prev, close) - abs(wiggle),
            "close": close,
            "volume": 100 + i,
        })
    return out


def _series(symbol, tf, n=80, trend=0.0):
    return CandleSeries(symbol, tf, _candles(n, tf.minutes, trend=trend))


def _board(trend=0.3, n=80):
    series_by_tf = {
        TimeFrame.M5: _series("BTC", TimeFrame.M5, n=n, trend=trend),
        TimeFrame.M60: _series("BTC", TimeFrame.M60, n=n, trend=trend),
    }
    return compute_board("BTC", series_by_tf)


def test_board_has_rows_for_each_timeframe():
    board = _board()
    assert board["symbol"] == "BTC"
    tfs = {row["timeframe"] for row in board["rows"]}
    assert tfs == {"5m", "1h"}
    # one row per (timeframe, indicator) pair
    assert len(board["rows"]) == 2 * len(BOARD_INDICATORS)
    for tf_value in ("5m", "1h"):
        names = [r["name"] for r in board["rows"] if r["timeframe"] == tf_value]
        assert names == BOARD_INDICATORS
    assert board["generated_at"]


def test_votes_match_normalized_signs():
    board = _board()
    for row in board["rows"]:
        norm = row["normalized"]
        if norm is None:
            assert row["vote"] == "neutral"
            assert row["strength"] == 0.0
        elif norm > VOTE_THRESHOLD:
            assert row["vote"] == "buy"
            assert row["strength"] == abs(norm)
        elif norm < -VOTE_THRESHOLD:
            assert row["vote"] == "sell"
            assert row["strength"] == abs(norm)
        else:
            assert row["vote"] == "neutral"
            assert row["strength"] == abs(norm)


def test_consensus_counts_add_up():
    board = _board()
    consensus = board["consensus"]
    assert set(consensus) == {"buy", "sell", "neutral"}
    assert sum(consensus.values()) == len(board["rows"])
    recount = {"buy": 0, "sell": 0, "neutral": 0}
    for row in board["rows"]:
        recount[row["vote"]] += 1
    assert recount == consensus


def test_uptrend_produces_buy_votes():
    board = _board(trend=0.5)
    momentum_rows = [r for r in board["rows"] if r["name"] == "MOMENTUM"]
    assert momentum_rows and all(r["vote"] == "buy" for r in momentum_rows)
    assert board["consensus"]["buy"] > 0


def test_short_series_yields_neutral_rows_not_crash():
    series_by_tf = {TimeFrame.M5: _series("BTC", TimeFrame.M5, n=10)}
    board = compute_board("BTC", series_by_tf)
    assert len(board["rows"]) == len(BOARD_INDICATORS)
    # too few bars for calculate_all: everything except the last-candle
    # direction (computed straight from the candles) is a neutral None row
    for row in board["rows"]:
        if row["name"] == "CANDLE_DIR":
            continue
        assert row["vote"] == "neutral" and row["value"] is None
    assert board["consensus"]["neutral"] >= len(board["rows"]) - 1


def test_extended_indicators_have_values_with_enough_data():
    series_by_tf = {TimeFrame.M60: _series("BTC", TimeFrame.M60, n=250, trend=0.2)}
    board = compute_board("BTC", series_by_tf)
    by_name = {r["name"]: r for r in board["rows"]}
    assert by_name["STOCH_D"]["value"] is not None
    assert by_name["ATR_REGIME"]["value"] is not None
    assert by_name["SMA200_TREND"]["value"] is not None
    # steady uptrend: close is above SMA200 -> positive raw value
    assert by_name["SMA200_TREND"]["value"] > 0
