"""Tests for fetch_binance_history pagination and the optimizer's Binance cache.

No real network: requests.get is monkeypatched throughout.
"""

import json
import time
from datetime import datetime, timedelta, timezone

import pytest

import binance_data
from binance_data import fetch_binance_history

FIVE_MIN_MS = 5 * 60 * 1000
BASE_MS = 1_700_000_000_000  # 2023-11-14T22:13:20Z


def _kline(open_ms, close=100.5):
    """Raw Binance kline row (only the first 6 fields matter to us)."""
    return [open_ms, "100.0", "101.0", "99.0", str(close), "12.5",
            open_ms + FIVE_MIN_MS - 1, "0", 0, "0", "0", "0"]


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(binance_data.time, "sleep", lambda s: None)


def _serve_pages(monkeypatch, pages, fail_from_page=None):
    """Monkeypatch requests.get to serve `pages` in order; records params."""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(dict(params))
        if fail_from_page is not None and len(calls) >= fail_from_page:
            raise binance_data.requests.exceptions.ConnectionError("boom")
        served = fake_get.served
        fake_get.served += 1
        return FakeResponse(pages[served])

    fake_get.served = 0
    monkeypatch.setattr(binance_data.requests, "get", fake_get)
    return calls


def test_pagination_walks_start_time_forward(monkeypatch):
    page1 = [_kline(BASE_MS + i * FIVE_MIN_MS) for i in range(5)]
    page2 = [_kline(BASE_MS + i * FIVE_MIN_MS) for i in range(5, 10)]
    page3 = [_kline(BASE_MS + i * FIVE_MIN_MS) for i in range(10, 12)]  # short page ends loop
    calls = _serve_pages(monkeypatch, [page1, page2, page3])

    end_ms = BASE_MS + 100 * FIVE_MIN_MS
    candles = fetch_binance_history(
        "BTC", interval="5m", start_ms=BASE_MS, end_ms=end_ms, page_limit=5
    )

    assert len(calls) == 3
    assert calls[0]["startTime"] == BASE_MS
    assert calls[1]["startTime"] == page1[-1][0] + 1
    assert calls[2]["startTime"] == page2[-1][0] + 1
    assert all(c["symbol"] == "BTCUSDT" and c["interval"] == "5m" and c["limit"] == 5
               for c in calls)
    # startTime strictly increases page over page
    starts = [c["startTime"] for c in calls]
    assert starts == sorted(starts) and len(set(starts)) == 3
    assert len(candles) == 12


def test_output_ascending_deduped_and_shaped(monkeypatch):
    page1 = [_kline(BASE_MS + i * FIVE_MIN_MS) for i in range(5)]
    # page2 re-serves page1's last kline (dup) plus 3 new ones
    page2 = [_kline(BASE_MS + i * FIVE_MIN_MS) for i in range(4, 8)]
    _serve_pages(monkeypatch, [page1, page2])

    candles = fetch_binance_history(
        "BTC", interval="5m", start_ms=BASE_MS,
        end_ms=BASE_MS + 100 * FIVE_MIN_MS, page_limit=5,
    )

    assert len(candles) == 8  # 5 + 4 - 1 dup
    ts_list = [c["timestamp"] for c in candles]
    assert ts_list == sorted(ts_list)
    assert len(set(ts_list)) == len(ts_list)

    first = candles[0]
    assert set(first) == {"timestamp", "open", "high", "low", "close", "volume"}
    for key in ("open", "high", "low", "close", "volume"):
        assert isinstance(first[key], float)
    # OPEN time of the kline, UTC, ISO without offset
    assert first["timestamp"] == datetime.fromtimestamp(
        BASE_MS / 1000, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%S")
    datetime.strptime(first["timestamp"], "%Y-%m-%dT%H:%M:%S")  # parseable


def test_partial_results_returned_after_failed_retry(monkeypatch):
    page1 = [_kline(BASE_MS + i * FIVE_MIN_MS) for i in range(5)]
    calls = _serve_pages(monkeypatch, [page1], fail_from_page=2)

    candles = fetch_binance_history(
        "BTC", interval="5m", start_ms=BASE_MS,
        end_ms=BASE_MS + 100 * FIVE_MIN_MS, page_limit=5,
    )

    # 1 successful page + 2 failed attempts (original + one retry) for page 2
    assert len(calls) == 3
    assert calls[1]["startTime"] == calls[2]["startTime"] == page1[-1][0] + 1
    assert len(candles) == 5
    assert [c["timestamp"] for c in candles] == sorted(c["timestamp"] for c in candles)


# ── optimizer cache-merge logic ──


def _candle(dt):
    return {"timestamp": dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 3.0}


def test_fresh_cache_fetches_only_tail_and_merges(monkeypatch, tmp_path):
    from optimizer import run

    monkeypatch.setattr(run, "_DATA_DIR", tmp_path)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    cached = [_candle(now - timedelta(hours=h)) for h in (3, 2, 1)]  # newest 1h old
    (tmp_path / "binance_hist_1h.json").write_text(json.dumps(cached))

    newest_ms = int((now - timedelta(hours=1)).timestamp() * 1000)
    tail = [_candle(now - timedelta(hours=1)), _candle(now)]  # overlaps newest cached

    fetch_calls = []

    def fake_fetch(symbol="BTCUSDT", interval="5m", days=730, start_ms=None, **kw):
        fetch_calls.append({"symbol": symbol, "interval": interval,
                            "days": days, "start_ms": start_ms})
        return tail

    monkeypatch.setattr(binance_data, "fetch_binance_history", fake_fetch)

    candles = run._binance_history_cached("1h")

    # tail fetch only: startTime = newest cached candle, no full 730d walk
    assert len(fetch_calls) == 1
    assert fetch_calls[0]["start_ms"] == newest_ms
    assert fetch_calls[0]["interval"] == "1h"

    ts_list = [c["timestamp"] for c in candles]
    assert ts_list == sorted(ts_list)
    assert len(set(ts_list)) == len(ts_list)
    assert len(candles) == 4  # 3 cached + 2 tail - 1 overlap
    # cache file rewritten with the merged series
    assert json.loads((tmp_path / "binance_hist_1h.json").read_text()) == candles


def test_stale_cache_triggers_full_refetch(monkeypatch, tmp_path):
    from optimizer import run

    monkeypatch.setattr(run, "_DATA_DIR", tmp_path)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    stale = [_candle(now - timedelta(hours=48))]
    (tmp_path / "binance_hist_5m.json").write_text(json.dumps(stale))

    fetch_calls = []

    def fake_fetch(symbol="BTCUSDT", interval="5m", days=730, start_ms=None, **kw):
        fetch_calls.append({"days": days, "start_ms": start_ms})
        return [_candle(now)]

    monkeypatch.setattr(binance_data, "fetch_binance_history", fake_fetch)

    candles = run._binance_history_cached("5m")

    assert len(fetch_calls) == 1
    assert fetch_calls[0]["start_ms"] is None  # full 730d window, not a tail fetch
    assert fetch_calls[0]["days"] == 730
    assert candles == [_candle(now)]


def test_missing_cache_triggers_full_refetch_and_writes_cache(monkeypatch, tmp_path):
    from optimizer import run

    monkeypatch.setattr(run, "_DATA_DIR", tmp_path / "data")  # dir does not exist yet
    now = datetime.now(timezone.utc).replace(microsecond=0)
    fresh = [_candle(now - timedelta(minutes=5)), _candle(now)]

    fetch_calls = []

    def fake_fetch(symbol="BTCUSDT", interval="5m", days=730, start_ms=None, **kw):
        fetch_calls.append(start_ms)
        return list(fresh)

    monkeypatch.setattr(binance_data, "fetch_binance_history", fake_fetch)

    candles = run._binance_history_cached("4h")

    assert fetch_calls == [None]
    assert candles == fresh
    cache_file = tmp_path / "data" / "binance_hist_4h.json"
    assert json.loads(cache_file.read_text()) == fresh
