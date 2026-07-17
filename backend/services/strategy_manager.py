"""Strategy management service - extracted from main.py"""
import os
import math
import database as db

# Global strategy manager - loaded once
_strategy_manager = None


def get_symbol_strategy(symbol: str) -> str:
    """Get strategy for symbol - delegates to state"""
    from services.state import get_symbol_strategy as _get
    result = _get(symbol)
    # Also check DB for per-symbol strategy
    strategy_key = f"STRATEGY_{symbol}"
    db_strategy = db.get_setting(strategy_key)
    if db_strategy:
        return db_strategy
    return result


def set_symbol_strategy(symbol: str, strategy_id: str):
    """Set strategy for symbol - delegates to state"""
    from services.state import set_symbol_strategy as _set
    _set(symbol, strategy_id)
    # Also save to DB
    strategy_key = f"STRATEGY_{symbol}"
    db.set_setting(strategy_key, strategy_id, "user")


def get_strategy_manager(force_reload: bool = False):
    """Get or create the JSON-based strategy manager."""
    global _strategy_manager

    if _strategy_manager is None or force_reload:
        try:
            from strategy import load_strategies_from_file

            # Load from local strategies.json in project root
            json_path = os.path.join(os.path.dirname(__file__), "..", "strategies.json")
            if os.path.exists(json_path):
                _strategy_manager = load_strategies_from_file(json_path)
                print(f"[STRATEGY] Loaded {len(_strategy_manager.strategies)} strategies from JSON")
            else:
                print(f"[STRATEGY] JSON config not found at {json_path}")
                _strategy_manager = None
        except Exception as e:
            print(f"[STRATEGY] Failed to load JSON strategies: {e}")
            _strategy_manager = None

    return _strategy_manager


def analyze_with_new_strategy(symbol: str, candles: list, current_price: float,
                              requested_strategy: str = None, atr_percent: float = None,
                              vix_value: float = None, series: dict = None) -> dict:
    """
    Analyze using new JSON-based strategy module.
    Returns dict with direction, score, confidence, etc. or None if not available.

    Score semantics (FIXED):
    - raw_score  = compute_score() result, already in [-1, 1] by weight normalization
    - direction  = from get_signal() which already applies min_score threshold ONCE
    - confidence = how far above min_score the signal is, mapped to [0, 1]
                   formula: (|raw_score| - min_score) / (1 - min_score)
                   A signal that just barely passes -> confidence ~0
                   A max-strength signal (|score|=1) -> confidence ~1
    - score (returned) = direction_sign * |raw_score|  (keeps [-1,1] range, no squashing)
    """
    manager = get_strategy_manager()
    if not manager:
        return None

    # Find strategy - use requested one or find any for symbol
    strategy = None
    if requested_strategy:
        # User specifically requested this JSON strategy
        json_id = requested_strategy.replace("JSON:", "")
        if json_id in manager.strategies:
            strategy = manager.strategies[json_id]
            # Only print on first call (check if already printed this session)
            if not getattr(analyze_with_new_strategy, "_logged", False):
                print(f"[STRATEGY] Using requested JSON strategy: {json_id}")
                analyze_with_new_strategy._logged = True
    else:
        # Default: use enabled strategy for this symbol
        for s in manager.get_enabled_strategies():
            if s.symbol.upper() == symbol.upper():
                strategy = s
                break

        # If no enabled, try any for this symbol
        if not strategy:
            for s in manager.strategies.values():
                if s.symbol.upper() == symbol.upper():
                    strategy = s
                    break

    if not strategy:
        return None

    if not candles:
        return None

    # ── SignalEngine path: stateless, deterministic, multi-timeframe ──
    # No streaming indicator re-feeding here anymore: indicators are computed
    # from the candle window itself, so live and backtest cannot drift.
    from datetime import datetime

    from services.candle_store import CandleSeries, _drop_forming  # noqa: PLC0415
    from strategy.engine import MarketSnapshot, SignalEngine, compute_base_atr_percent
    from timeframes import TimeFrame

    engine = SignalEngine(strategy.config)
    base_tf = engine.base_timeframe()

    if series is None:
        # Single-TF callers (backtester CLI, legacy API) pass a plain candle list
        base_series = CandleSeries(symbol, base_tf, list(candles))
        series = {base_tf: base_series}

    ts = datetime.utcnow()
    snapshot = MarketSnapshot(
        symbol=symbol,
        ts=ts,
        price=current_price,
        series=series,
        vix=vix_value,
    )

    # Filters still come from the strategy's FilterChain (volatility, VIX, session)
    if atr_percent is None:
        atr_percent = compute_base_atr_percent(snapshot, base_tf)
    evaluation = engine.evaluate(snapshot)
    if evaluation.direction == "neutral":
        return None

    # Filters run AFTER evaluation so direction-sensitive filters see the real
    # side (the old call hardcoded 'long' for every entry, shorts included)
    base_candles = series.get(base_tf).candles if series.get(base_tf) else list(candles)
    if base_candles:
        filters_passed, failed_filters = strategy.filters.check_all(
            base_candles[-1], symbol, evaluation.direction,
            atr_percent=atr_percent,
            vix_value=vix_value
        )
        if not filters_passed:
            print(f"[FILTERS] {symbol}: Failed filters: {failed_filters}")
            return None

    per_tf_components = [{
        'type': 'technical',
        'name': f'{tf} score',
        'value': t.score if t.score is not None else 0.0,
        'description': f'{tf}: score={t.score:.3f} weight={t.weight}' if t.score is not None else f'{tf}: no data',
        'confidence': evaluation.confidence,
    } for tf, t in evaluation.per_timeframe.items()]

    return {
        'direction': evaluation.direction,
        'score': evaluation.score,                  # [-1, 1] with full spread
        'confidence': evaluation.confidence,        # [0, 1]
        'technical_score': evaluation.score,
        'agreement': evaluation.agreement,
        'components': [{
            'type': 'technical',
            'name': f'JSON Strategy ({strategy.id})',
            'value': evaluation.score,
            'description': (
                f'Score: {evaluation.score:.3f}, Dir: {evaluation.direction}, '
                f'Conf: {evaluation.confidence:.2f}, TF agreement: {evaluation.agreement:.2f}'
            ),
            'confidence': evaluation.confidence
        }] + per_tf_components,
        'exits': evaluation.exits,
        'per_timeframe': {
            tf: {'score': t.score, 'weight': t.weight, 'bars': t.bars,
                 'indicators': {n: {'raw': d['raw'], 'normalized': d['normalized']}
                                for n, d in t.indicators.items()}}
            for tf, t in evaluation.per_timeframe.items()
        },
        'strategy_id': strategy.id,
    }
