"""Stateless per-window indicator snapshots.

One indicator implementation for the whole system: everything is computed by
`TechnicalIndicators` (indicators.py) from a window of CLOSED candles. Same
candles in -> same values out, in live, backtest and the optimizer alike. No
streaming state, so nothing can be corrupted by re-feeding.
"""

from typing import Dict, List, Optional

from indicators import TechnicalIndicators

# Fixed normalization ranges (midpoint maps to 0). Values outside clamp to +-1.
INDICATOR_RANGES: Dict[str, tuple] = {
    "RSI": (0, 100),
    "STOCH": (0, 100),
    "STOCH_RSI": (0, 100),
    "ADX": (-100, 100),  # signed by DI dominance
    "MACD": (-1, 1),     # histogram as % of price
    "MOMENTUM": (-10, 10),
    "DIVERGENCE": (-1, 1),
    "CANDLE_DIR": (-1, 1),
    "HTF_CANDLE": (-1, 1),  # legacy alias of CANDLE_DIR
    "SMA_CROSS": (-5, 5),   # % distance sma20 vs sma50
    "BB_POSITION": (-1, 1),
    "VOLUME_RATIO": (-3, 3),
    "CANDLE_PATTERN": (-1, 1),
    "STOCH_D": (0, 100),        # smoothed stoch-RSI %D
    "ATR_REGIME": (-1, 1),      # ATR% vs its recent mean (volatility expansion)
    "SMA200_TREND": (-10, 10),  # % distance close vs SMA200
}


def _normalize(name: str, raw: Optional[float]) -> Optional[float]:
    if raw is None:
        return None
    lo, hi = INDICATOR_RANGES.get(name, (-1, 1))
    mid = (lo + hi) / 2
    half = (hi - lo) / 2
    if half <= 0:
        return 0.0
    return max(-1.0, min(1.0, (raw - mid) / half))


def _raw_value(name: str, ind: dict, candles: List[dict]) -> Optional[float]:
    """Extract one indicator's raw value from the calculate_all dict."""
    if name == "RSI":
        return ind.get("rsi_14")
    if name == "MACD":
        # histogram as % of price - scale-invariant across BTC (~60k) and XAG (~30)
        macd = ind.get("macd") or {}
        hist = macd.get("histogram") if isinstance(macd, dict) else macd
        close = candles[-1].get("close") if candles else None
        if hist is None or not close:
            return None
        return hist / close * 100
    if name == "MOMENTUM":
        # momentum_10 is an absolute price change; normalize to % of price
        mom = ind.get("momentum_10")
        close = candles[-1].get("close") if candles else None
        if mom is None or not close:
            return None
        return mom / close * 100
    if name == "ADX":
        # ADX alone is non-directional strength; sign it by DI dominance so it
        # contributes direction * strength instead of a constant bearish drift
        adx = ind.get("adx") or {}
        if not isinstance(adx, dict):
            return None
        strength = adx.get("adx")
        if strength is None:
            return None
        plus_di, minus_di = adx.get("plus_di", 0) or 0, adx.get("minus_di", 0) or 0
        return strength if plus_di >= minus_di else -strength
    if name in ("STOCH", "STOCH_RSI"):
        st = ind.get("stoch_rsi") or {}
        return st.get("k") if isinstance(st, dict) else st
    if name == "DIVERGENCE":
        div = ind.get("divergence") or {}
        return div.get("divergence") if isinstance(div, dict) else div
    if name in ("CANDLE_DIR", "HTF_CANDLE"):
        if not candles:
            return None
        last = candles[-1]
        o, c = last.get("open"), last.get("close")
        if not o:
            return None
        return 1.0 if c > o else (-1.0 if c < o else 0.0)
    if name == "SMA_CROSS":
        sma20, sma50 = ind.get("sma_20"), ind.get("sma_50")
        if not sma20 or not sma50:
            return None
        return (sma20 - sma50) / sma50 * 100
    if name == "BB_POSITION":
        bb = ind.get("bollinger_bands") or {}
        upper, lower = bb.get("upper"), bb.get("lower")
        close = candles[-1].get("close") if candles else None
        if not upper or not lower or close is None or upper == lower:
            return None
        # -1 at lower band, +1 at upper band
        return max(-1.0, min(1.0, (close - (upper + lower) / 2) / ((upper - lower) / 2)))
    if name == "VOLUME_RATIO":
        vp = ind.get("volume_profile") or {}
        ratio = vp.get("vol_ratio") if isinstance(vp, dict) else None
        return (ratio - 1.0) if ratio is not None else None
    if name == "CANDLE_PATTERN":
        cp = ind.get("candlestick_patterns") or {}
        return cp.get("net_bias") if isinstance(cp, dict) else None
    if name == "STOCH_D":
        st = ind.get("stoch_rsi") or {}
        return st.get("d") if isinstance(st, dict) else None
    if name == "ATR_REGIME":
        # Current ATR (last 14 true ranges) vs mean TR of the recent window.
        # > 0 = volatility expanding, < 0 = contracting. Stateless per window.
        if len(candles) < 30:
            return None
        window = candles[-50:]
        trs = []
        for prev, cur in zip(window, window[1:]):
            h, l, pc = cur.get("high"), cur.get("low"), prev.get("close")
            if h is None or l is None or pc is None:
                return None
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if len(trs) < 15:
            return None
        baseline = sum(trs) / len(trs)
        if baseline <= 0:
            return None
        current = sum(trs[-14:]) / 14
        return current / baseline - 1.0
    if name == "SMA200_TREND":
        if len(candles) < 200:
            return None
        closes = [c.get("close") for c in candles[-200:]]
        if any(c is None for c in closes):
            return None
        sma200 = sum(closes) / 200
        if sma200 <= 0:
            return None
        return (closes[-1] - sma200) / sma200 * 100
    return None


def compute_indicator_snapshot(candles: List[dict], specs: List[dict]) -> Dict[str, dict]:
    """Compute {name: {raw, normalized, weight}} for the requested indicator specs.

    `specs` are entries from a strategy's per-timeframe `indicators` list:
    {"name": "RSI", "weight": 2.0, ...}. Unknown names yield raw=None and are
    skipped by the score engine.
    """
    if not candles:
        return {}
    ind = TechnicalIndicators.calculate_all(candles, period=14) or {}
    out: Dict[str, dict] = {}
    for spec in specs:
        name = (spec.get("name") or "").upper()
        if not name:
            continue
        raw = _raw_value(name, ind, candles)
        out[name] = {
            "raw": raw,
            "normalized": _normalize(name, raw),
            "weight": spec.get("weight", 0.0),
        }
    return out


def compute_atr_percent(candles: List[dict]) -> Optional[float]:
    """ATR as % of last close - used by filters and exit sizing."""
    if not candles or len(candles) < 15:
        return None
    ind = TechnicalIndicators.calculate_all(candles, period=14) or {}
    atr = ind.get("atr_14")
    close = candles[-1].get("close")
    if atr is None or not close:
        return None
    return atr / close * 100
