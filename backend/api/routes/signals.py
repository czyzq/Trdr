"""Signals API routes"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from models import SignalResponse
from services.trading_engine import generate_signals
from app.logging import log_event

router = APIRouter(tags=["signals"])


@router.get("/api/signals", response_model=SignalResponse)
async def get_signals():
    """Fetch real trading signals."""
    log_event("Generating signals via API...", "info")
    signals = await generate_signals()
    return SignalResponse(signals=signals)


def _find_strategy_for_symbol(symbol: str):
    """Resolve the symbol's strategy: enabled first, then any (mirrors
    services.strategy_manager.analyze_with_new_strategy)."""
    from services.strategy_manager import get_strategy_manager

    manager = get_strategy_manager()
    if not manager:
        return None
    for s in manager.get_enabled_strategies():
        if s.symbol.upper() == symbol.upper():
            return s
    for s in manager.strategies.values():
        if s.symbol.upper() == symbol.upper():
            return s
    return None


@router.get("/api/signals/board")
async def get_signal_board(symbol: str = "BTC"):
    """Multi-timeframe indicator board for one symbol."""
    from services.candle_store import get_candle_store
    from strategy.board import compute_board
    from strategy.engine import SignalEngine

    strategy = _find_strategy_for_symbol(symbol)
    if strategy is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"No strategy configured for symbol '{symbol}'"},
        )

    try:
        engine = SignalEngine(strategy.config)
        store = get_candle_store()
        series_by_tf = {}
        for tf in engine.required_timeframes():
            series_by_tf[tf] = await store.get_series(symbol, tf)
        return compute_board(symbol, series_by_tf)
    except Exception as e:
        log_event(f"Board computation failed for {symbol}: {e}", "error")
        return JSONResponse(status_code=500, content={"error": str(e)})
