"""The ONE backtest engine.

Replays closed candles bar-by-bar through the SAME `SignalEngine` the live
loop uses. No parallel scoring implementation, no substitute exit overlay:
entries come from `SignalEngine.evaluate`, exit levels from the strategy's
own exit config, fills from the `CostModel` (spread, gap-aware stops,
slippage, overnight swap).

No-lookahead invariant: the snapshot for bar i contains only candles whose
period CLOSED at or before bar i's close, on every timeframe.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from services.candle_store import CandleSeries, _parse_ts
from strategy.engine import MarketSnapshot, SignalEngine
from strategy.filters import FilterChain
from strategy.snapshot import compute_atr_percent
from timeframes import TimeFrame

from .costs import CostModel
from .metrics import BacktestReport, TradeRecord

WARMUP_BARS = 60
SERIES_WINDOW = 150  # bars per TF handed to the engine each step


@dataclass
class _OpenPosition:
    direction: str          # buy | sell
    size: float
    entry_price: float      # actual fill (spread included)
    entry_mid: float        # mid price at entry (bar close)
    entry_ts: datetime
    entry_bar: int
    tp_price: Optional[float]
    sl_price: Optional[float]
    signal_score: float
    confidence: float


def _position_size(balance: float, entry: float, sl: Optional[float], config: dict, symbol: str) -> float:
    """Risk-based sizing: risk_pct of balance against the SL distance.
    Leverage from config, capped by the instrument's cap. Applied exactly once."""
    risk_cfg = config.get("risk", {})
    risk_pct = risk_cfg.get("risk_per_trade_percent", 1.5)
    from app.config import INSTRUMENTS

    max_lev = INSTRUMENTS.get(symbol, {}).get("leverage", 10)
    leverage = min(risk_cfg.get("leverage", 1.0) or 1.0, max_lev)
    risk_amount = balance * risk_pct / 100
    per_unit_risk = abs(entry - sl) if sl else entry * 0.02
    if per_unit_risk <= 0:
        per_unit_risk = entry * 0.02
    # size in units so an SL hit loses ~risk_pct of balance; leverage only caps notional
    size = risk_amount / per_unit_risk
    max_size = balance * leverage / entry
    return max(0.0, min(size, max_size))


class _SeriesCursor:
    """Incremental no-lookahead view over one timeframe's candles."""

    def __init__(self, symbol: str, tf: TimeFrame, candles: List[dict]):
        self.symbol = symbol
        self.tf = tf
        bar = timedelta(minutes=tf.minutes)
        parsed = []
        for c in candles:
            ts = _parse_ts(c.get("timestamp", ""))
            if ts is not None:
                parsed.append((ts + bar, c))  # (close_time, candle)
        parsed.sort(key=lambda x: x[0])
        self.closes = [p[0] for p in parsed]
        self.candles = [p[1] for p in parsed]
        self._idx = 0

    def advance_to(self, ts: datetime) -> None:
        while self._idx < len(self.closes) and self.closes[self._idx] <= ts:
            self._idx += 1

    def series(self) -> CandleSeries:
        lo = max(0, self._idx - SERIES_WINDOW)
        return CandleSeries(self.symbol, self.tf, self.candles[lo:self._idx])


def run_backtest(
    strategy_config: dict,
    candles: Dict[str, List[dict]],
    cost_model: Optional[CostModel] = None,
    initial_balance: float = 3000.0,
    max_hold_bars: int = 200,
) -> BacktestReport:
    """`candles` maps timeframe value ("5m", "1h", ...) or TimeFrame -> candle list.
    Must include the strategy's base timeframe; other TFs are optional context."""
    engine = SignalEngine(strategy_config)
    symbol = strategy_config.get("symbol", "?")
    base_tf = engine.base_timeframe()
    cost_model = cost_model or CostModel(symbol)
    # strategy config wins over the caller default - exits belong to the strategy
    max_hold_bars = strategy_config.get("exits", {}).get("max_hold_bars", max_hold_bars)

    # normalize keys to TimeFrame
    by_tf: Dict[TimeFrame, List[dict]] = {}
    for key, lst in candles.items():
        tf = key if isinstance(key, TimeFrame) else TimeFrame(str(key))
        by_tf[tf] = lst
    if base_tf not in by_tf:
        raise ValueError(f"backtest needs candles for base timeframe {base_tf.value}")

    cursors = {tf: _SeriesCursor(symbol, tf, lst) for tf, lst in by_tf.items()}
    base_candles = cursors[base_tf].candles
    base_closes = cursors[base_tf].closes
    if len(base_candles) <= WARMUP_BARS:
        raise ValueError(f"not enough base candles ({len(base_candles)}) for warmup {WARMUP_BARS}")

    filters = FilterChain(strategy_config.get("filters", {}), services={})
    norm_cfg = engine.config

    balance = initial_balance
    position: Optional[_OpenPosition] = None
    trades: List[TradeRecord] = []
    equity_curve: List[float] = []

    def close_position(pos: _OpenPosition, fill: float, ts: datetime, bar_i: int,
                       reason: str, exit_mid: float) -> None:
        nonlocal balance, position
        # net = what the account actually gains: fill-to-fill P&L plus financing
        fill_pnl = (fill - pos.entry_price) * pos.size if pos.direction == "buy" \
            else (pos.entry_price - fill) * pos.size
        swap = cost_model.swap_cost(pos.entry_price * pos.size, pos.direction, pos.entry_ts, ts)
        net = fill_pnl + swap
        # gross = mid-to-mid P&L; costs = gross - net (spread+slippage+swap), so the
        # identity net == gross - costs holds by construction
        gross = (exit_mid - pos.entry_mid) * pos.size if pos.direction == "buy" \
            else (pos.entry_mid - exit_mid) * pos.size
        costs = gross - net
        balance += net
        trades.append(TradeRecord(
            symbol=symbol,
            direction=pos.direction,
            entry_ts=pos.entry_ts.isoformat(),
            exit_ts=ts.isoformat(),
            entry_price=round(pos.entry_price, 6),
            exit_price=round(fill, 6),
            size=round(pos.size, 6),
            gross_pnl_usd=round(gross, 2),
            costs_usd=round(costs, 2),
            net_pnl_usd=round(net, 2),
            exit_reason=reason,
            bars_held=bar_i - pos.entry_bar,
            signal_score=pos.signal_score,
            confidence=pos.confidence,
        ))
        position = None

    for i in range(WARMUP_BARS, len(base_candles)):
        bar = base_candles[i]
        bar_close_ts = base_closes[i]
        for cursor in cursors.values():
            cursor.advance_to(bar_close_ts)

        # ── exits first (position opened on an EARLIER bar's close) ──
        if position is not None:
            direction = position.direction
            hit_sl = hit_tp = False
            if position.sl_price:
                hit_sl = bar["low"] <= position.sl_price if direction == "buy" else bar["high"] >= position.sl_price
            if position.tp_price:
                hit_tp = bar["high"] >= position.tp_price if direction == "buy" else bar["low"] <= position.tp_price
            if hit_sl:  # worst-case: SL before TP when both hit in one bar
                mid = min(position.sl_price, bar["open"]) if direction == "buy" else max(position.sl_price, bar["open"])
                fill = cost_model.stop_fill(position.sl_price, bar["open"], direction)
                close_position(position, fill, bar_close_ts, i, "sl", exit_mid=mid)
            elif hit_tp:
                fill = cost_model.tp_fill(position.tp_price, bar["open"], direction)
                close_position(position, fill, bar_close_ts, i, "tp", exit_mid=position.tp_price)
            elif i - position.entry_bar >= max_hold_bars:
                fill = cost_model.exit_fill(bar["close"], direction)
                close_position(position, fill, bar_close_ts, i, "timeout", exit_mid=bar["close"])

        # ── entries ──
        if position is None:
            snapshot = MarketSnapshot(
                symbol=symbol,
                ts=bar_close_ts,
                price=bar["close"],
                series={tf: cur.series() for tf, cur in cursors.items()},
            )
            base_series = snapshot.series[base_tf]
            atr_pct = compute_atr_percent(base_series.candles)
            evaluation = engine.evaluate(snapshot)
            if evaluation.direction != "neutral":
                passed, _failed = filters.check_all(
                    bar, symbol, evaluation.direction, atr_percent=atr_pct, vix_value=None)
                if passed:
                    direction = "buy" if evaluation.direction == "long" else "sell"
                    entry = cost_model.entry_fill(bar["close"], direction)
                    exits = evaluation.exits or {}
                    tp, sl = exits.get("tp_price"), exits.get("sl_price")
                    size = _position_size(balance, entry, sl, norm_cfg, symbol)
                    if size > 0:
                        position = _OpenPosition(
                            direction=direction,
                            size=size,
                            entry_price=entry,
                            entry_mid=bar["close"],
                            entry_ts=bar_close_ts,
                            entry_bar=i,
                            tp_price=tp,
                            sl_price=sl,
                            signal_score=evaluation.score,
                            confidence=evaluation.confidence,
                        )

        # ── mark-to-market equity ──
        unrealized = 0.0
        if position is not None:
            mid = bar["close"]
            unrealized = (mid - position.entry_price) * position.size if position.direction == "buy" \
                else (position.entry_price - mid) * position.size
            # accrue financing so multi-night holds show it in drawdown, not as an exit jump
            unrealized += cost_model.swap_cost(
                position.entry_price * position.size, position.direction, position.entry_ts, bar_close_ts)
        equity_curve.append(round(balance + unrealized, 2))

    # force-close whatever is still open at the last bar
    if position is not None:
        last_bar = base_candles[-1]
        fill = cost_model.exit_fill(last_bar["close"], position.direction)
        close_position(position, fill, base_closes[-1], len(base_candles) - 1, "end_of_data",
                       exit_mid=last_bar["close"])
        if equity_curve:
            equity_curve[-1] = round(balance, 2)

    report = BacktestReport(
        symbol=symbol,
        strategy_id=norm_cfg.get("id", "unknown"),
        timeframe=base_tf.value,
        window_from=base_candles[WARMUP_BARS].get("timestamp", ""),
        window_to=base_candles[-1].get("timestamp", ""),
        initial_balance=initial_balance,
        final_balance=round(balance, 2),
        trades=trades,
        equity_curve=equity_curve,
    )
    report.compute_metrics(base_tf.minutes)
    return report
