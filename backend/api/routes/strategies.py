"""strategies API routes - extracted from main.py"""
from fastapi import APIRouter, Body, Query
from typing import Optional
from pydantic import BaseModel
from services.state import get_symbol_strategy, set_symbol_strategy, get_all_strategy_selections, get_instruments
from app.logging import log_event

router = APIRouter()


def get_strategy_manager():
    """Lazy import get_strategy_manager to avoid circular import"""
    from main import get_strategy_manager
    return get_strategy_manager()


@router.get("/api/strategies")
async def get_strategies():
    """List all available trading strategies."""
    from strategies import list_strategies as old_list_strategies
    manager = get_strategy_manager()
    json_strategies = [
        {"id": sid, "name": s.name, "timeframe": getattr(s, 'timeframe', '5m')}
        for sid, s in manager.strategies.items()
    ]
    old_strategies = old_list_strategies()
    return {"strategies": old_strategies + json_strategies}


@router.get("/api/strategies/{symbol}")
async def get_strategy_for_symbol(symbol: str):
    """Get the currently selected strategy for a symbol."""
    return {"symbol": symbol, "strategy": get_symbol_strategy(symbol)}


@router.post("/api/strategies/{symbol}")
async def set_strategy_for_symbol(symbol: str, strategy_id: str = Body(...)):
    """Set the strategy for a symbol."""
    set_symbol_strategy(symbol, strategy_id)
    log_event(f"[STRATEGY] Set {symbol} -> {strategy_id}", "info")
    return {"symbol": symbol, "strategy": strategy_id}


@router.get("/api/strategies-all")
async def get_all_strategy_selections():
    """Get strategy selection for all symbols."""
    instruments = get_instruments()
    return {"selections": {sym: get_symbol_strategy(sym) for sym in instruments}}
