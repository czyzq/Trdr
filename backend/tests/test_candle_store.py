"""Tests for the per-(symbol, timeframe) CandleStore."""

import asyncio
from datetime import datetime, timedelta

import pytest

from services.candle_store import (
    AGGREGATED_FROM,
    BASE_TIMEFRAMES,
    CandleSeries,
    CandleStore,
    _drop_forming,
)
from timeframes import TimeFrame


def _mk(ts: datetime, price: float = 100.0, volume: float = 10.0) -> dict:
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S"),
        "open": price,
        "high": price + 1,
        "low": price - 1,
        "close": price,
        "volume": volume,
    }


def _series_5m(n: int, end: datetime) -> list:
    return [_mk(end - timedelta(minutes=5 * (n - i)), 100.0 + i) for i in range(n)]


class FakeProvider:
    def __init__(self, candles_by_res=None):
        self.candles_by_res = candles_by_res or {}
        self.calls = []

    async def get_candles(self, symbol, resolution, count):
        self.calls.append((symbol, resolution, count))
        return list(self.candles_by_res.get(resolution, []))


# ── CandleSeries ──


def test_merge_is_idempotent_and_sorted():
    now = datetime(2026, 1, 1, 12, 0, 0)
    series = CandleSeries("XAU", TimeFrame.M5)
    candles = _series_5m(10, now)
    assert series.merge(candles) == 10
    assert series.merge(candles) == 0  # idempotent
    assert series.merge(list(reversed(candles))) == 0
    timestamps = [c["timestamp"] for c in series.candles]
    assert timestamps == sorted(timestamps)


def test_merge_replaces_same_timestamp():
    now = datetime(2026, 1, 1, 12, 0, 0)
    series = CandleSeries("XAU", TimeFrame.M5)
    series.merge([_mk(now, 100.0)])
    series.merge([_mk(now, 105.0)])
    assert len(series.candles) == 1
    assert series.candles[0]["close"] == 105.0


def test_truncate_to_excludes_unclosed_bars():
    now = datetime(2026, 1, 1, 12, 0, 0)
    series = CandleSeries("XAU", TimeFrame.M5)
    series.merge(_series_5m(10, now))
    # at 11:58, the bar opened at 11:55 has not closed yet
    cut = series.truncate_to(datetime(2026, 1, 1, 11, 58, 0))
    assert all(c["timestamp"] <= "2026-01-01T11:50:00" for c in cut.candles)


def test_drop_forming_strips_open_bar():
    now = datetime(2026, 1, 1, 12, 2, 0)
    candles = _series_5m(5, datetime(2026, 1, 1, 12, 0, 0)) + [_mk(datetime(2026, 1, 1, 12, 0, 0))]
    closed = _drop_forming(candles, TimeFrame.M5, now)
    # bar opened at 12:00 closes at 12:05 -> must be dropped at 12:02
    assert all(c["timestamp"] < "2026-01-01T12:00:00" for c in closed)


# ── CandleStore ──


@pytest.mark.asyncio
async def test_get_series_fetches_then_caches():
    now = datetime.utcnow().replace(second=0, microsecond=0)
    provider = FakeProvider({"5": _series_5m(60, now)})
    store = CandleStore(provider)
    s1 = await store.get_series("XAU", TimeFrame.M5, min_bars=50)
    assert len(s1.candles) >= 50
    calls_after_first = len(provider.calls)
    # immediately again: no new bar can exist -> no new fetch
    await store.get_series("XAU", TimeFrame.M5, min_bars=50)
    assert len(provider.calls) == calls_after_first


@pytest.mark.asyncio
async def test_aggregated_timeframe_uses_base_fetch_only():
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    provider = FakeProvider({"5": _series_5m(90, now)})
    store = CandleStore(provider)
    s15 = await store.get_series("XAU", TimeFrame.M15, min_bars=10)
    # only the 5m base was fetched from the network
    assert all(res == "5" for _, res, _ in provider.calls)
    assert len(s15.candles) > 0
    # 15m bars must be 3x5m aggregates: volume sums
    assert s15.candles[-1]["volume"] == pytest.approx(30.0)


@pytest.mark.asyncio
async def test_agg_mapping_covers_non_base_tfs():
    for tf in (TimeFrame.M15, TimeFrame.M30, TimeFrame.H4):
        assert tf in AGGREGATED_FROM
        assert AGGREGATED_FROM[tf] in BASE_TIMEFRAMES


@pytest.mark.asyncio
async def test_store_never_returns_forming_bar():
    now = datetime.utcnow()
    # provider returns a forming bar stamped "now"
    candles = _series_5m(60, now - timedelta(minutes=5)) + [_mk(now)]
    provider = FakeProvider({"5": candles})
    store = CandleStore(provider)
    series = await store.get_series("XAU", TimeFrame.M5, min_bars=10)
    last = series.last_closed_ts()
    assert last is not None
    assert last + timedelta(minutes=5) <= datetime.utcnow() + timedelta(seconds=1)


@pytest.mark.asyncio
async def test_vix_cached_across_calls(monkeypatch):
    import services.candle_store as cs

    calls = {"n": 0}

    def fake_vix(symbol):
        calls["n"] += 1
        return {"value": 18.0, "name": "VIX", "change_pct": 0.1}

    import historical_data

    monkeypatch.setattr(historical_data, "get_volatility_index", fake_vix)
    store = CandleStore(FakeProvider())
    for _ in range(5):
        data = await store.get_vix("SPX")
    assert data["value"] == 18.0
    assert calls["n"] == 1
