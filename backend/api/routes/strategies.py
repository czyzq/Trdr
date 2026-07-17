"""Strategies API routes - extracted from main.py"""
from fastapi import APIRouter, Body, Query
from services.state import get_symbol_strategy, set_symbol_strategy, get_all_strategy_selections, get_instruments
from app.logging import log_event

router = APIRouter()


def get_strategy_manager():
    """Lazy import get_strategy_manager to avoid circular import"""
    from main import get_strategy_manager
    return get_strategy_manager()


@router.get("/api/strategies")
async def get_strategies():
    """List all available trading strategies (JSON)."""
    json_strategies = []
    manager = get_strategy_manager()
    if manager:
        for s in manager.strategies.values():
            json_strategies.append({
                'id': f"JSON:{s.id}",
                'name': s.name,
                'description': f"JSON-based strategy for {s.symbol}",
                'source': 'JSON',
                'symbol': s.symbol,
                'timeframe': s.timeframe,
                'enabled': s.enabled
            })
    return {"strategies": json_strategies}


@router.get("/api/strategy/{symbol}")
async def get_strategy_for_symbol(symbol: str):
    """Get the active strategy for a symbol."""
    return {"symbol": symbol, "strategy": get_symbol_strategy(symbol)}


@router.post("/api/strategy/{symbol}")
async def set_strategy_for_symbol(
    symbol: str, 
    strategy_id: str = Query(None),
    body_strategy_id: str = Body(None, embed=True)
):
    """Set the strategy for a symbol via query param or body."""
    # Accept either query param or body
    strategy_id = strategy_id or body_strategy_id
    if not strategy_id:
        return {"error": "strategy_id is required (query param or body)"}

    json_id = strategy_id.replace("JSON:", "")
    manager = get_strategy_manager()
    if manager and json_id in manager.strategies:
        set_symbol_strategy(symbol, strategy_id)
        log_event(f"[STRATEGY] {symbol} → JSON:{json_id} (JSON strategy)", "event")
        return {"symbol": symbol, "strategy": strategy_id, "note": "JSON strategy will be used automatically"}

    available = list(manager.strategies.keys()) if manager else []
    return {"error": f"Unknown strategy: {strategy_id}. Available: {available}"}


@router.get("/api/strategy-selections")
async def get_all_strategy_selections():
    """Get strategy selection for all symbols."""
    instruments = get_instruments()
    return {sym: get_symbol_strategy(sym) for sym in instruments}


# POST /api/strategies/backtest-json lives in api/routes/backtest.py
