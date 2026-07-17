"""The one signal engine - pure, deterministic, shared by live and backtest.

`SignalEngine.evaluate(snapshot)` has no I/O, no globals, no mutable state:
the live loop and the backtester differ only in how they build the
`MarketSnapshot`. Multi-timeframe scoring happens here.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional

from timeframes import TimeFrame

from .exits import ExitEngine
from .snapshot import compute_atr_percent, compute_indicator_snapshot

# Minimum closed bars a timeframe needs before it may contribute to the score.
MIN_BARS_PER_TF = 30


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    ts: datetime
    price: float
    series: Dict[TimeFrame, "object"]  # tf -> CandleSeries (closed candles up to ts only)
    vix: Optional[float] = None
    context: dict = field(default_factory=dict)


@dataclass
class TfScore:
    timeframe: str
    score: Optional[float]          # [-1, 1] or None if insufficient data
    weight: float
    indicators: Dict[str, dict]     # name -> {raw, normalized, weight}
    bars: int


@dataclass
class Evaluation:
    symbol: str
    strategy_id: str
    direction: Literal["long", "short", "neutral"]
    score: float                    # [-1, 1], 0 when neutral
    confidence: float               # [0, 1]
    agreement: float                # [0, 1] weighted TF sign agreement
    per_timeframe: Dict[str, TfScore]
    filters_failed: List[str] = field(default_factory=list)
    vetoed_by: Optional[str] = None
    exits: dict = field(default_factory=dict)
    reason: str = ""


def normalize_strategy_config(config: dict) -> dict:
    """Return a config in multi-timeframe form.

    Legacy single-TF configs ({"timeframe": "5m", "score": {...}}) are
    converted to an equivalent one-entry `timeframes` block so every existing
    strategy keeps working unchanged. Multi-TF configs pass through after
    validation. Raises ValueError on structural errors - bad configs must fail
    at load, not silently at runtime.
    """
    if "timeframes" in config:
        tfs = config["timeframes"]
        if not isinstance(tfs, dict) or not tfs:
            raise ValueError(f"strategy {config.get('id')}: 'timeframes' must be a non-empty dict")
        total_weight = 0.0
        for tf_name, block in tfs.items():
            TimeFrame(tf_name)  # raises ValueError on unknown timeframe
            if block.get("role") == "veto":
                veto = block.get("veto") or {}
                if not veto.get("indicator"):
                    raise ValueError(f"strategy {config.get('id')}: veto TF '{tf_name}' needs veto.indicator")
            else:
                weight = block.get("weight", 0.0)
                total_weight += weight
                if weight > 0 and not block.get("indicators"):
                    raise ValueError(f"strategy {config.get('id')}: TF '{tf_name}' has weight but no indicators")
        if total_weight <= 0:
            raise ValueError(f"strategy {config.get('id')}: no timeframe carries positive weight")
        if "base_timeframe" not in config:
            raise ValueError(f"strategy {config.get('id')}: multi-TF config needs base_timeframe")
        TimeFrame(config["base_timeframe"])
        config.setdefault("combine", {})
        return config

    # Legacy single-TF form
    tf = config.get("timeframe", "5m")
    tf_value = tf.value if hasattr(tf, "value") else str(tf)
    score_cfg = config.get("score", {})
    indicators = score_cfg.get("indicators", [])
    if not indicators:
        raise ValueError(f"strategy {config.get('id')}: no score indicators configured")
    converted = dict(config)
    converted["base_timeframe"] = tf_value
    converted["timeframes"] = {tf_value: {"weight": 1.0, "indicators": indicators}}
    converted["combine"] = {
        "method": "weighted_sum",
        "min_score": score_cfg.get("min_score", 0.01),
        "min_agreement": 0.0,          # single TF: agreement is trivially 1
        "conflict_policy": "ignore",
    }
    return converted


def _check_veto(block: dict, direction: str, indicators: Dict[str, dict]) -> bool:
    """True if the veto rule PASSES (trade allowed)."""
    veto = block.get("veto") or {}
    name = (veto.get("indicator") or "").upper()
    data = indicators.get(name)
    if data is None or data.get("normalized") is None:
        return True  # no data -> no veto (fail open, the TF is optional context)
    value = data["normalized"]
    rule = veto.get("long_requires" if direction == "long" else "short_requires")
    if not rule:
        return True
    op, _, threshold = rule.partition(" ")
    try:
        threshold = float(threshold)
    except ValueError:
        return True
    if op == ">":
        return value > threshold
    if op == ">=":
        return value >= threshold
    if op == "<":
        return value < threshold
    if op == "<=":
        return value <= threshold
    return True


class SignalEngine:
    """Deterministic multi-timeframe scorer for one strategy config."""

    def __init__(self, strategy_config: dict):
        self.config = normalize_strategy_config(dict(strategy_config))
        self.strategy_id = self.config.get("id", "unknown")
        self.combine = self.config.get("combine", {})
        self.min_score = self.combine.get("min_score", 0.01)
        self.min_agreement = self.combine.get("min_agreement", 0.0)
        self.conflict_policy = self.combine.get("conflict_policy", "dampen")

    # ── scoring ──

    def _score_timeframes(self, snapshot: MarketSnapshot) -> Dict[str, TfScore]:
        out: Dict[str, TfScore] = {}
        for tf_name, block in self.config["timeframes"].items():
            tf = TimeFrame(tf_name)
            series = snapshot.series.get(tf)
            candles = series.candles if series is not None else []
            specs = block.get("indicators", [])
            if block.get("role") == "veto":
                veto_spec = [{"name": block["veto"]["indicator"], "weight": 0.0}]
                specs = specs + veto_spec
            if len(candles) < MIN_BARS_PER_TF:
                out[tf_name] = TfScore(tf_name, None, block.get("weight", 0.0), {}, len(candles))
                continue
            indicators = compute_indicator_snapshot(candles, specs)
            score = None
            weighted = [
                (d["normalized"], d["weight"])
                for d in indicators.values()
                if d["normalized"] is not None and d["weight"] > 0
            ]
            total_w = sum(w for _, w in weighted)
            if total_w > 0:
                score = max(-1.0, min(1.0, sum(v * w for v, w in weighted) / total_w))
            out[tf_name] = TfScore(tf_name, score, block.get("weight", 0.0), indicators, len(candles))
        return out

    def _combined_score(self, tf_scores: Dict[str, TfScore]) -> Optional[float]:
        weighted = [(t.score, t.weight) for t in tf_scores.values() if t.score is not None and t.weight > 0]
        total_w = sum(w for _, w in weighted)
        if total_w <= 0:
            return None
        return sum(s * w for s, w in weighted) / total_w

    def _agreement(self, tf_scores: Dict[str, TfScore], combined: float) -> float:
        """Weighted share of scoring TFs whose sign matches the combined score."""
        sign = 1 if combined >= 0 else -1
        num = 0.0
        den = 0.0
        for t in tf_scores.values():
            if t.score is None or t.weight <= 0:
                continue
            den += t.weight
            if (t.score >= 0 and sign > 0) or (t.score < 0 and sign < 0):
                num += t.weight
        return num / den if den > 0 else 0.0

    def _direction_from_config(self, tf_scores: Dict[str, TfScore], combined: float) -> Optional[str]:
        """Direction per the config's direction_mode (legacy rsi_momentum supported)."""
        if self.config.get("direction_mode") == "rsi_momentum":
            dir_cfg = self.config.get("direction_config", {})
            base_tf = self.config["base_timeframe"]
            base = tf_scores.get(base_tf)
            if base is None:
                return None
            rsi = (base.indicators.get("RSI") or {}).get("raw")
            mom = (base.indicators.get("MOMENTUM") or {}).get("raw")
            rsi_oversold = dir_cfg.get("rsi_oversold", 40)
            rsi_overbought = dir_cfg.get("rsi_overbought", 60)
            mom_threshold = dir_cfg.get("momentum_threshold", 0)
            if rsi is not None and rsi < rsi_oversold:
                return "long"
            if mom is not None and mom > mom_threshold:
                return "long"
            if rsi is not None and rsi > rsi_overbought:
                return "short"
            if mom is not None and mom < mom_threshold:
                return "short"
            return None
        # score_only
        if combined >= self.min_score:
            return "long"
        if combined <= -self.min_score:
            return "short"
        return None

    # ── public API ──

    def evaluate(self, snapshot: MarketSnapshot) -> Evaluation:
        tf_scores = self._score_timeframes(snapshot)

        def neutral(reason: str, vetoed_by: Optional[str] = None,
                    filters_failed: Optional[List[str]] = None,
                    agreement: float = 0.0) -> Evaluation:
            return Evaluation(
                symbol=snapshot.symbol,
                strategy_id=self.strategy_id,
                direction="neutral",
                score=0.0,
                confidence=0.0,
                agreement=agreement,
                per_timeframe=tf_scores,
                filters_failed=filters_failed or [],
                vetoed_by=vetoed_by,
                reason=reason,
            )

        combined = self._combined_score(tf_scores)
        if combined is None:
            return neutral("insufficient data on all scoring timeframes")

        agreement = self._agreement(tf_scores, combined)

        # conflict policy between timeframes
        effective = combined
        if agreement < self.min_agreement:
            if self.conflict_policy == "veto":
                return neutral(
                    f"timeframe agreement {agreement:.2f} < {self.min_agreement}",
                    agreement=agreement,
                )
            if self.conflict_policy == "dampen":
                effective = combined * agreement

        direction = self._direction_from_config(tf_scores, effective)
        if direction is None or abs(effective) < self.min_score:
            return neutral(f"score {effective:.3f} below min_score {self.min_score}", agreement=agreement)

        # veto timeframes
        for tf_name, block in self.config["timeframes"].items():
            if block.get("role") != "veto":
                continue
            tf_data = tf_scores.get(tf_name)
            if tf_data is None:
                continue
            if not _check_veto(block, direction, tf_data.indicators):
                return neutral(f"vetoed by {tf_name}", vetoed_by=tf_name, agreement=agreement)

        # confidence: agreement-weighted distance above the threshold
        score_range = max(1.0 - self.min_score, 1e-6)
        confidence = max(0.0, min(1.0, (abs(effective) - self.min_score) / score_range))
        if self.min_agreement > 0 or len([t for t in tf_scores.values() if t.weight > 0]) > 1:
            confidence *= agreement

        # exits from the strategy's own ExitEngine config (percent-based prices)
        exit_engine = ExitEngine(self.config.get("exits", {}), htf_indicator=None)
        exits = exit_engine.initialize_position(
            position_id=f"eval_{snapshot.symbol}",
            entry_price=snapshot.price,
            direction=1 if direction == "long" else -1,
        )

        signed = abs(effective) if direction == "long" else -abs(effective)
        return Evaluation(
            symbol=snapshot.symbol,
            strategy_id=self.strategy_id,
            direction=direction,
            score=max(-1.0, min(1.0, signed)),
            confidence=confidence,
            agreement=agreement,
            per_timeframe=tf_scores,
            exits=exits or {},
            reason="ok",
        )

    def required_timeframes(self) -> List[TimeFrame]:
        return [TimeFrame(tf) for tf in self.config["timeframes"].keys()]

    def base_timeframe(self) -> TimeFrame:
        return TimeFrame(self.config["base_timeframe"])


def compute_base_atr_percent(snapshot: MarketSnapshot, base_tf: TimeFrame) -> Optional[float]:
    series = snapshot.series.get(base_tf)
    if series is None:
        return None
    return compute_atr_percent(series.candles)
