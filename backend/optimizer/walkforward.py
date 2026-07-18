"""Rolling walk-forward folds with an embargo gap between train and validate.

Folds are cut on the BASE timeframe by bar index, then every other timeframe
is filtered by TIMESTAMP against the fold's real time window - higher
timeframes keep their full history up to the window end (past context is
legitimate; months-stale context from index-ratio slicing is not).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from services.candle_store import _parse_ts


@dataclass
class Fold:
    train: Dict[str, list]      # tf -> candles
    validate: Dict[str, list]


# fold spec per base timeframe: (train_bars, embargo_bars, validate_bars)
FOLD_SPECS = {
    "5m": (6048, 288, 2016),    # 21d / 1d / 7d of 5m bars
    "15m": (2016, 96, 672),
    "1h": (2160, 24, 1080),     # 90d / 1d / 45d - reversion needs sample room
    "1d": (365, 5, 90),
}
N_FOLDS = 3


def _ts(candle: dict):
    return _parse_ts(candle.get("timestamp", ""))


def _window(candles_by_tf: Dict[str, list], base_tf: str, start_idx: int, end_idx: int) -> Optional[Dict[str, list]]:
    """Base TF sliced by index; every other TF filtered to timestamps <= window end
    (full past history retained for HTF warmup/context - no lookahead)."""
    base = candles_by_tf[base_tf]
    segment = base[start_idx:end_idx]
    if not segment:
        return None
    end_ts = _ts(segment[-1])
    if end_ts is None:
        return None
    out = {base_tf: segment}
    for tf, lst in candles_by_tf.items():
        if tf == base_tf:
            continue
        out[tf] = [c for c in lst if (_ts(c) or end_ts) <= end_ts]
    return out


def make_folds(candles_by_tf: Dict[str, list], base_tf: str, n_folds: int = N_FOLDS) -> List[Fold]:
    train_n, embargo_n, val_n = FOLD_SPECS.get(base_tf, FOLD_SPECS["5m"])
    base = candles_by_tf[base_tf]
    fold_span = train_n + embargo_n + val_n
    folds = []
    # newest fold ends at the end of data; step back by val_n per fold
    for k in range(n_folds):
        end = len(base) - k * val_n
        start = end - fold_span
        if start < 0:
            break
        train = _window(candles_by_tf, base_tf, start, start + train_n)
        validate = _window(candles_by_tf, base_tf, start + train_n + embargo_n, end)
        if train is None or validate is None:
            break
        folds.append(Fold(train=train, validate=validate))
    return folds
