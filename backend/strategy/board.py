"""Multi-timeframe indicator board.

Renders every catalog indicator across all of a strategy's timeframes into a
flat vote table for the dashboard. Purely stateless: it reuses
`compute_indicator_snapshot` (strategy/snapshot.py), so the board can never
disagree with what the signal engine itself would compute from the same
candles.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from strategy.snapshot import compute_indicator_snapshot

# Full catalog shown on the board (superset of what any one strategy scores).
BOARD_INDICATORS: List[str] = [
    "RSI",
    "MACD",
    "MOMENTUM",
    "ADX",
    "STOCH",
    "STOCH_D",
    "SMA_CROSS",
    "SMA200_TREND",
    "BB_POSITION",
    "DIVERGENCE",
    "VOLUME_RATIO",
    "ATR_REGIME",
    "CANDLE_PATTERN",
    "CANDLE_DIR",
]

VOTE_THRESHOLD = 0.15


def _vote(normalized: Optional[float]) -> str:
    if normalized is None:
        return "neutral"
    if normalized > VOTE_THRESHOLD:
        return "buy"
    if normalized < -VOTE_THRESHOLD:
        return "sell"
    return "neutral"


def compute_board(symbol: str, series_by_tf: dict) -> dict:
    """Build the indicator board for one symbol.

    `series_by_tf` maps timeframes.TimeFrame -> services.candle_store.CandleSeries
    (closed candles only). Returns rows for every (timeframe, indicator) pair
    plus buy/sell/neutral consensus counts.
    """
    specs = [{"name": name, "weight": 1.0} for name in BOARD_INDICATORS]
    rows: List[dict] = []
    consensus: Dict[str, int] = {"buy": 0, "sell": 0, "neutral": 0}

    for tf in sorted(series_by_tf.keys(), key=lambda t: t.minutes):
        series = series_by_tf[tf]
        candles = series.candles if series is not None else []
        snapshot = compute_indicator_snapshot(candles, specs)
        for name in BOARD_INDICATORS:
            data = snapshot.get(name) or {}
            normalized = data.get("normalized")
            vote = _vote(normalized)
            consensus[vote] += 1
            rows.append(
                {
                    "name": name,
                    "timeframe": tf.value,
                    "value": data.get("raw"),
                    "normalized": normalized,
                    "vote": vote,
                    "strength": abs(normalized) if normalized is not None else 0.0,
                }
            )

    return {
        "symbol": symbol,
        "rows": rows,
        "consensus": consensus,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
