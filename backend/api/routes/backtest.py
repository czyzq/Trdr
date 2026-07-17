"""Backtest API routes - thin wrapper over backtest.engine.run_backtest"""
import asyncio
import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

router = APIRouter()


def fetch_candles_for_config(strategy_config: dict, symbol: str, days: int) -> dict:
    """Fetch candles from Yahoo for every timeframe the strategy needs."""
    from historical_data import fetch_yahoo_historical
    from strategy.engine import SignalEngine

    engine = SignalEngine(strategy_config)
    candles_by_tf = {}
    for tf in engine.required_timeframes():
        fetched = fetch_yahoo_historical(symbol, period_days=days + 10, interval=tf.yahoo_interval)
        if fetched:
            candles_by_tf[tf] = fetched
    return candles_by_tf


@router.post("/api/strategies/backtest-json")
async def backtest_from_json(
    request: Request,
    symbol: str = Query(None, description="Symbol (defaults to strategy config symbol)"),
    days: int = Query(30, description="Number of days of history"),
    initial_balance: float = Query(3000.0, description="Initial balance"),
):
    """Run a backtest on a JSON strategy config posted in the request body.

    Body may be a bare strategy config or {"strategies": [...]} (strategies.json format).
    """
    try:
        body = await request.body()
        config = json.loads(body)

        strategy_config = None
        if isinstance(config, dict) and "strategies" in config:
            candidates = [
                s for s in config.get("strategies", [])
                if symbol is None or s.get("symbol", "").upper() == symbol.upper()
            ]
            # Prefer an enabled strategy
            strategy_config = next((s for s in candidates if s.get("enabled", False)), None)
            if strategy_config is None and candidates:
                strategy_config = candidates[0]
        elif isinstance(config, dict):
            strategy_config = config

        if not strategy_config:
            return JSONResponse(
                {"error": f"No strategy found in body for symbol: {symbol}"}, status_code=400
            )

        sym = (symbol or strategy_config.get("symbol", "")).upper()
        if not sym:
            return JSONResponse({"error": "No symbol provided"}, status_code=400)
        strategy_config = {**strategy_config, "symbol": sym}

        candles_by_tf = await asyncio.to_thread(
            fetch_candles_for_config, strategy_config, sym, days
        )
        if not candles_by_tf:
            return JSONResponse({"error": f"No candles available for {sym}"}, status_code=400)

        from backtest.engine import run_backtest

        report = await asyncio.to_thread(
            run_backtest,
            strategy_config,
            candles_by_tf,
            initial_balance=initial_balance,
        )
        return {"report": report.to_doc()}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
