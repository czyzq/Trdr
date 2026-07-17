"""Rolling walk-forward folds with an embargo gap between train and validate."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Fold:
    train: Dict[str, list]      # tf -> candles
    validate: Dict[str, list]


# fold spec per base timeframe: (train_bars, embargo_bars, validate_bars)
FOLD_SPECS = {
    "5m": (6048, 288, 2016),    # 21d / 1d / 7d of 5m bars
    "15m": (2016, 96, 672),
    "1h": (2160, 24, 720),      # 90d / 1d / 30d
    "1d": (365, 5, 90),
}
N_FOLDS = 3


def make_folds(candles_by_tf: Dict[str, list], base_tf: str, n_folds: int = N_FOLDS) -> List[Fold]:
    """Slice every timeframe by the base TF's fold boundaries (by index ratio)."""
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
        t0, t1 = start, start + train_n
        v0, v1 = t1 + embargo_n, end
        ratios = {tf: len(lst) / len(base) for tf, lst in candles_by_tf.items()}
        train = {tf: lst[int(t0 * r):int(t1 * r)] for (tf, lst), r in
                 zip(candles_by_tf.items(), ratios.values())}
        validate = {tf: lst[int(v0 * r):int(v1 * r)] for (tf, lst), r in
                    zip(candles_by_tf.items(), ratios.values())}
        folds.append(Fold(train=train, validate=validate))
    return folds
