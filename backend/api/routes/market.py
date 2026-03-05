"""market API routes - extracted from main.py"""
from fastapi import APIRouter, Query
from datetime import datetime
from services.state import get_instruments as _get_instruments
from services import is_market_open, get_market_hours
from app.logging import log_event
from timezone import now_warsaw

router = APIRouter(prefix="/api")


def get_data_provider():
    """Lazy import data_provider to avoid circular import"""
    from main import data_provider
    return data_provider


def get_async_load_candle_history():
    """Lazy import async_load_candle_history to avoid circular import"""
    from main import async_load_candle_history
    return async_load_candle_history


def get_async_count_candles():
    """Lazy import async_count_candles to avoid circular import"""
    from main import async_count_candles
    return async_count_candles


def get_async_get_candle_date_range():
    """Lazy import async_get_candle_date_range to avoid circular import"""
    from main import async_get_candle_date_range
    return async_get_candle_date_range


@router.get("/instruments")
async def get_instruments():
    """Get all instruments with their settings."""
    instruments = _get_instruments()
    return {
        symbol: {
            "name": info.get("name", symbol),
            "leverage": info.get("leverage", 1),
            "lot_size": info.get("lot_size", 1),
            "pip_size": info.get("pip_size", 0.01),
            "asset_class": info.get("asset_class", ""),
            "trailing_stop": info.get("trailing_stop", False),
            "market_open": is_market_open(symbol),
            "market_hours": get_market_hours(symbol),
        }
        for symbol, info in instruments.items()
    }


@router.post("/instruments/{symbol}/leverage")
async def set_leverage(symbol: str, leverage: int):
    """Update leverage for an instrument."""
    instruments = _get_instruments()
    if symbol not in instruments:
        return {"error": f"Unknown instrument: {symbol}"}
    if leverage < 1 or leverage > 100:
        return {"error": "Leverage must be between 1 and 100"}
    instruments[symbol]["leverage"] = leverage
    return {"symbol": symbol, "leverage": leverage}


@router.get("/quote/{symbol}")
async def get_quote(symbol: str):
    """Get current quote for a symbol."""
    try:
        data_provider = get_data_provider()
        quote = await data_provider.get_quote(symbol)
        return quote
    except Exception as e:
        return {"error": str(e)}


@router.get("/chart/{symbol}")
async def get_chart_data(symbol: str, resolution: str = "60", count: int = 100):
    """Get OHLCV chart data for a symbol."""
    try:
        data_provider = get_data_provider()
        candles = await data_provider.get_candles(symbol, resolution, count)
        return {"symbol": symbol, "candles": candles, "count": len(candles)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/candles/{symbol}")
async def get_candle_history(
    symbol: str,
    resolution: str = Query("60", description="Resolution: 1, 5, 15, 30, 60, D"),
    count: int = Query(100, ge=1, le=1000),
    from_time: str = Query(None, description="ISO timestamp or YYYY-MM-DD"),
    to_time: str = Query(None, description="ISO timestamp or YYYY-MM-DD"),
):
    """Get historical candle data."""
    try:
        async_load_candle_history = get_async_load_candle_history()
        candles = await async_load_candle_history(symbol, resolution, count, from_time, to_time)
        return {"symbol": symbol, "resolution": resolution, "candles": candles, "count": len(candles)}
    except Exception as e:
        return {"error": str(e)}
