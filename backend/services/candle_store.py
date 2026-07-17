"""Per-(symbol, timeframe) candle store.

The single supplier of candle series to the signal engine:
- keeps CLOSED candles only (the forming bar is never included; live price
  comes from the quote cache instead)
- refetches only when a new bar can exist, not on a flat TTL
- fetches only base timeframes (5m, 1h, 1d) from the network; 15m and 4h are
  aggregated locally from stored base candles
- warm-starts from Mongo history so a restart does not refetch everything
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import database
from timeframes import TimeFrame


def _parse_ts(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.strptime(ts.replace("Z", "").split("+")[0].split(".")[0], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(ts[:10], "%Y-%m-%d")
        except ValueError:
            return None


@dataclass
class CandleSeries:
    """Ascending, deduped, closed-candles-only series for one (symbol, timeframe)."""

    symbol: str
    timeframe: TimeFrame
    candles: List[dict] = field(default_factory=list)

    def merge(self, new_candles: List[dict]) -> int:
        """Idempotent merge by timestamp; replaces existing bars, appends new ones."""
        if not new_candles:
            return 0
        by_ts = {c.get("timestamp"): c for c in self.candles}
        added = 0
        for c in new_candles:
            ts = c.get("timestamp")
            if not ts:
                continue
            if ts not in by_ts:
                added += 1
            by_ts[ts] = c
        self.candles = [by_ts[ts] for ts in sorted(by_ts)]
        return added

    def last_closed_ts(self) -> Optional[datetime]:
        if not self.candles:
            return None
        return _parse_ts(self.candles[-1].get("timestamp", ""))

    def window(self, n: int) -> List[dict]:
        return self.candles[-n:]

    def truncate_to(self, ts: datetime) -> "CandleSeries":
        """Series containing only bars CLOSED at `ts` (for backtest snapshots)."""
        bar = timedelta(minutes=self.timeframe.minutes)
        kept = []
        for c in self.candles:
            c_ts = _parse_ts(c.get("timestamp", ""))
            if c_ts is not None and c_ts + bar <= ts:
                kept.append(c)
        return CandleSeries(self.symbol, self.timeframe, kept)


# Base TFs hit the network; the rest aggregate locally from a base TF.
BASE_TIMEFRAMES = (TimeFrame.M5, TimeFrame.M60, TimeFrame.D1)
AGGREGATED_FROM: Dict[TimeFrame, TimeFrame] = {
    TimeFrame.M15: TimeFrame.M5,
    TimeFrame.M30: TimeFrame.M5,
    TimeFrame.H4: TimeFrame.M60,
}


def _drop_forming(candles: List[dict], tf: TimeFrame, now: Optional[datetime] = None) -> List[dict]:
    """Strip any bar whose period has not fully elapsed yet."""
    if not candles:
        return []
    now = now or datetime.utcnow()
    bar = timedelta(minutes=tf.minutes)
    out = []
    for c in candles:
        ts = _parse_ts(c.get("timestamp", ""))
        if ts is not None and ts + bar <= now:
            out.append(c)
    return out


class CandleStore:
    def __init__(self, data_provider):
        self._provider = data_provider
        self._series: Dict[Tuple[str, str], CandleSeries] = {}
        self._locks: Dict[Tuple[str, str], asyncio.Lock] = {}
        self._vix_cache: Dict[str, tuple] = {}  # symbol -> (fetched_monotonic, data)

    def _lock_for(self, key: Tuple[str, str]) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def _get_or_create(self, symbol: str, tf: TimeFrame) -> CandleSeries:
        key = (symbol, tf.value)
        series = self._series.get(key)
        if series is None:
            series = CandleSeries(symbol, tf)
            # Warm start from Mongo so restarts don't refetch history
            try:
                history = database.load_candle_history(symbol, tf.db_resolution, limit=600)
                if history:
                    series.merge(_drop_forming(history, tf))
            except Exception:
                pass
            self._series[key] = series
        return series

    def _is_fresh(self, series: CandleSeries, now: Optional[datetime] = None) -> bool:
        """Fresh = no new bar can exist yet."""
        last = series.last_closed_ts()
        if last is None:
            return False
        now = now or datetime.utcnow()
        # next bar closes at last_open + 2 * bar_len (last bar close + one full bar)
        return now < last + timedelta(minutes=2 * series.timeframe.minutes)

    async def get_series(self, symbol: str, tf: TimeFrame, min_bars: int = 300) -> CandleSeries:
        key = (symbol, tf.value)
        async with self._lock_for(key):
            series = self._get_or_create(symbol, tf)
            if self._is_fresh(series) and len(series.candles) >= min(min_bars, 50):
                return series

            base_tf = AGGREGATED_FROM.get(tf)
            if base_tf is not None:
                await self._refresh_aggregated(series, base_tf, min_bars)
            else:
                await self._refresh_base(series, min_bars)
            return series

    async def _refresh_base(self, series: CandleSeries, min_bars: int) -> None:
        tf = series.timeframe
        try:
            fetched = await asyncio.wait_for(
                self._provider.get_candles(series.symbol, tf.db_resolution, max(min_bars, 100)),
                timeout=15.0,
            )
        except Exception:
            fetched = None
        if fetched:
            closed = _drop_forming(fetched, tf)
            added = series.merge(closed)
            if added:
                try:
                    await asyncio.to_thread(
                        database.store_candles, series.symbol, tf.db_resolution, closed, "candle_store"
                    )
                except Exception:
                    pass

    async def _refresh_aggregated(self, series: CandleSeries, base_tf: TimeFrame, min_bars: int) -> None:
        factor = series.timeframe.minutes // base_tf.minutes
        base = await self.get_series(series.symbol, base_tf, min_bars * factor)
        if not base.candles:
            return
        try:
            aggregated = database.aggregate_candles(base.candles, series.timeframe.db_resolution)
        except Exception:
            aggregated = []
        if aggregated:
            series.merge(_drop_forming(aggregated, series.timeframe))

    async def get_vix(self, symbol: str, ttl_sec: float = 300.0) -> Optional[dict]:
        """Volatility index, fetched at most once per TTL per index (not per scan per symbol)."""
        cached = self._vix_cache.get(symbol)
        if cached and time.monotonic() - cached[0] < ttl_sec:
            return cached[1]
        try:
            from historical_data import get_volatility_index

            data = await asyncio.to_thread(get_volatility_index, symbol)
        except Exception:
            data = None
        if data is None and symbol != "SPX":
            data = await self.get_vix("SPX", ttl_sec)
        self._vix_cache[symbol] = (time.monotonic(), data)
        return data


_store: Optional[CandleStore] = None


def get_candle_store() -> CandleStore:
    global _store
    if _store is None:
        from services.state import data_provider

        _store = CandleStore(data_provider)
    return _store
