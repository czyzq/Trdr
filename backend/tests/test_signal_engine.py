"""Tests for the multi-timeframe SignalEngine (strategy/engine.py)."""

import math
from datetime import datetime, timedelta

import pytest

from services.candle_store import CandleSeries
from strategy.engine import (
    Evaluation,
    MarketSnapshot,
    SignalEngine,
    normalize_strategy_config,
)
from strategy.snapshot import INDICATOR_RANGES, _normalize, compute_indicator_snapshot
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


def _series(symbol, tf, n=80, trend=0.0, end=None):
    return CandleSeries(symbol, tf, _candles(n, tf.minutes, end=end, trend=trend))


def _snapshot(series_map, price=100.0, symbol="BTC"):
    return MarketSnapshot(symbol=symbol, ts=datetime(2026, 1, 10, 12, 0, 0),
                          price=price, series=series_map)


def _cfg(**overrides):
    cfg = {
        "id": "test_mtf",
        "symbol": "BTC",
        "base_timeframe": "5m",
        "timeframes": {
            "5m": {"weight": 0.5, "indicators": [{"name": "MOMENTUM", "weight": 1.0}]},
            "1h": {"weight": 0.5, "indicators": [{"name": "MOMENTUM", "weight": 1.0}]},
        },
        "combine": {"min_score": 0.05, "min_agreement": 0.6, "conflict_policy": "dampen"},
        "exits": {"stop_loss": {"value": -2.0}, "take_profit": {"value": 4.0}},
    }
    cfg.update(overrides)
    return cfg


# ── normalization math ──


def test_normalize_midpoint_maps_to_zero():
    assert _normalize("RSI", 50) == pytest.approx(0.0)
    assert _normalize("RSI", 100) == pytest.approx(1.0)
    assert _normalize("RSI", 0) == pytest.approx(-1.0)
    assert _normalize("MOMENTUM", 5) == pytest.approx(0.5)
    assert _normalize("MOMENTUM", -20) == -1.0  # clamped


def test_snapshot_hand_computed_weighted_score():
    candles = _candles(80, 5, trend=0.3)
    specs = [{"name": "RSI", "weight": 2.0}, {"name": "MOMENTUM", "weight": 1.0}]
    snap = compute_indicator_snapshot(candles, specs)
    assert set(snap) == {"RSI", "MOMENTUM"}
    expected = (snap["RSI"]["normalized"] * 2.0 + snap["MOMENTUM"]["normalized"] * 1.0) / 3.0
    engine = SignalEngine(_cfg(timeframes={"5m": {"weight": 1.0, "indicators": specs}}))
    ev = engine.evaluate(_snapshot({TimeFrame.M5: CandleSeries("BTC", TimeFrame.M5, candles)}))
    tf_score = ev.per_timeframe["5m"].score
    assert tf_score == pytest.approx(max(-1, min(1, expected)))


# ── combination & agreement ──


def test_uptrend_on_both_tfs_gives_long():
    engine = SignalEngine(_cfg())
    ev = engine.evaluate(_snapshot({
        TimeFrame.M5: _series("BTC", TimeFrame.M5, trend=0.4),
        TimeFrame.M60: _series("BTC", TimeFrame.M60, trend=0.4),
    }))
    assert ev.direction == "long"
    assert ev.score > 0
    assert ev.agreement == pytest.approx(1.0)


def test_conflict_dampen_reduces_score():
    engine = SignalEngine(_cfg())
    ev_conflict = engine.evaluate(_snapshot({
        TimeFrame.M5: _series("BTC", TimeFrame.M5, trend=0.4),
        TimeFrame.M60: _series("BTC", TimeFrame.M60, trend=-0.4),
    }))
    # 50/50 conflict -> agreement 0.5 < 0.6 -> dampened score 0.5x, likely below min_score
    assert ev_conflict.agreement == pytest.approx(0.5)
    ev_aligned = engine.evaluate(_snapshot({
        TimeFrame.M5: _series("BTC", TimeFrame.M5, trend=0.4),
        TimeFrame.M60: _series("BTC", TimeFrame.M60, trend=0.4),
    }))
    assert abs(ev_conflict.score) < abs(ev_aligned.score)


def test_conflict_veto_forces_neutral():
    engine = SignalEngine(_cfg(combine={"min_score": 0.01, "min_agreement": 0.9,
                                        "conflict_policy": "veto"}))
    ev = engine.evaluate(_snapshot({
        TimeFrame.M5: _series("BTC", TimeFrame.M5, trend=0.4),
        TimeFrame.M60: _series("BTC", TimeFrame.M60, trend=-0.4),
    }))
    assert ev.direction == "neutral"
    assert "agreement" in ev.reason


def test_conflict_ignore_keeps_score():
    engine = SignalEngine(_cfg(combine={"min_score": 0.01, "min_agreement": 0.9,
                                        "conflict_policy": "ignore"}))
    ev = engine.evaluate(_snapshot({
        TimeFrame.M5: _series("BTC", TimeFrame.M5, trend=0.6),
        TimeFrame.M60: _series("BTC", TimeFrame.M60, trend=-0.1),
    }))
    # not forced neutral by agreement; direction decided by combined sign
    assert ev.direction in ("long", "short")


# ── veto timeframe ──


def test_daily_veto_blocks_long():
    cfg = _cfg()
    cfg["timeframes"]["1d"] = {
        "weight": 0.0,
        "role": "veto",
        # require strongly positive daily SMA_CROSS for longs; downtrend daily will fail it
        "veto": {"indicator": "SMA_CROSS", "long_requires": "> 0.5", "short_requires": "< 100"},
    }
    engine = SignalEngine(cfg)
    ev = engine.evaluate(_snapshot({
        TimeFrame.M5: _series("BTC", TimeFrame.M5, trend=0.4),
        TimeFrame.M60: _series("BTC", TimeFrame.M60, trend=0.4),
        TimeFrame.D1: _series("BTC", TimeFrame.D1, trend=-0.5),
    }))
    assert ev.direction == "neutral"
    assert ev.vetoed_by == "1d"


def test_missing_veto_data_fails_open():
    cfg = _cfg()
    cfg["timeframes"]["1d"] = {
        "weight": 0.0,
        "role": "veto",
        "veto": {"indicator": "SMA_CROSS", "long_requires": "> 0.5"},
    }
    engine = SignalEngine(cfg)
    # no 1d series supplied -> veto must not block
    ev = engine.evaluate(_snapshot({
        TimeFrame.M5: _series("BTC", TimeFrame.M5, trend=0.4),
        TimeFrame.M60: _series("BTC", TimeFrame.M60, trend=0.4),
    }))
    assert ev.direction == "long"


# ── legacy config conversion ──


def test_legacy_config_converts_to_single_tf():
    legacy = {
        "id": "legacy_1",
        "symbol": "XAU",
        "timeframe": "5m",
        "score": {"min_score": 0.25, "indicators": [{"name": "RSI", "weight": 1.0}]},
    }
    norm = normalize_strategy_config(legacy)
    assert norm["base_timeframe"] == "5m"
    assert list(norm["timeframes"]) == ["5m"]
    assert norm["combine"]["min_score"] == 0.25
    assert norm["combine"]["conflict_policy"] == "ignore"


def test_invalid_configs_fail_loud():
    with pytest.raises(ValueError):
        normalize_strategy_config({"id": "bad", "timeframes": {}, "base_timeframe": "5m"})
    with pytest.raises(ValueError):
        normalize_strategy_config({"id": "bad2", "timeframe": "5m", "score": {"indicators": []}})
    with pytest.raises(ValueError):
        normalize_strategy_config({
            "id": "bad3", "base_timeframe": "5m",
            "timeframes": {"7m": {"weight": 1.0, "indicators": [{"name": "RSI", "weight": 1}]}},
        })


def test_all_shipped_strategies_normalize():
    import json

    cfg = json.load(open("strategies.json"))
    for s in cfg["strategies"]:
        engine = SignalEngine(s)
        assert engine.base_timeframe() is not None


# ── determinism & no-lookahead ──


def test_evaluate_is_deterministic():
    engine = SignalEngine(_cfg())
    snap = _snapshot({
        TimeFrame.M5: _series("BTC", TimeFrame.M5, trend=0.3),
        TimeFrame.M60: _series("BTC", TimeFrame.M60, trend=0.3),
    })
    ev1 = engine.evaluate(snap)
    ev2 = engine.evaluate(snap)
    assert (ev1.direction, ev1.score, ev1.confidence, ev1.agreement) == (
        ev2.direction, ev2.score, ev2.confidence, ev2.agreement)


def test_no_lookahead_truncated_series_matches():
    """Bars after ts must not influence the evaluation."""
    eval_ts = datetime(2026, 1, 10, 12, 0, 0)
    full_5m = _candles(120, 5, end=eval_ts + timedelta(hours=3), trend=0.3)
    s_full = CandleSeries("BTC", TimeFrame.M5, full_5m).truncate_to(eval_ts)
    s_manual = CandleSeries("BTC", TimeFrame.M5,
                            [c for c in full_5m if c["timestamp"] <= "2026-01-10T11:55:00"])
    engine = SignalEngine(_cfg(timeframes={"5m": {"weight": 1.0,
                                                  "indicators": [{"name": "MOMENTUM", "weight": 1.0}]}}))
    ev_a = engine.evaluate(_snapshot({TimeFrame.M5: s_full}))
    ev_b = engine.evaluate(_snapshot({TimeFrame.M5: s_manual}))
    assert ev_a.score == pytest.approx(ev_b.score)
    assert ev_a.direction == ev_b.direction


def test_insufficient_data_yields_neutral():
    engine = SignalEngine(_cfg())
    ev = engine.evaluate(_snapshot({TimeFrame.M5: _series("BTC", TimeFrame.M5, n=5)}))
    assert ev.direction == "neutral"
    assert "insufficient" in ev.reason
