"""market API routes - extracted from main.py"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
from datetime import datetime


def create_market_endpoints(INSTRUMENTS, is_market_open_func, get_market_hours_func, log_event_func,
                            get_async_client_func, get_alpha_vantage_client_func,
                            async_load_candle_history_func, async_count_candles_func, 
                            async_get_candle_date_range_func, db_module,
                            now_warsaw_func, async_timed_func):
    """Factory function to create market endpoints with required dependencies."""
    
    router = APIRouter(prefix="/api")
    
    @router.get("/instruments")
    async def get_instruments():
        """Get all instruments with their settings (leverage, lot_size, etc.)."""
        return {
            symbol: {
                "name": info["name"],
                "leverage": info.get("leverage", 1),
                "lot_size": info.get("lot_size", 1),
                "pip_size": info.get("pip_size", 0.01),
                "asset_class": info.get("asset_class", ""),
                "trailing_stop": info.get("trailing_stop", False),
                "market_open": is_market_open_func(symbol),
                "market_hours": get_market_hours_func(symbol),
            }
            for symbol, info in INSTRUMENTS.items()
        }
    
    @router.post("/instruments/{symbol}/leverage")
    async def set_leverage(symbol: str, leverage: int):
        """Update leverage for an instrument. Valid values: 1-100."""
        if symbol not in INSTRUMENTS:
            return {"error": f"Unknown instrument: {symbol}"}
        if leverage < 1 or leverage > 100:
            return {"error": "Leverage must be between 1 and 100"}
        INSTRUMENTS[symbol]["leverage"] = leverage
        log_event_func(f"[SETTINGS] {symbol} leverage set to x{leverage}", "event")
        return {"symbol": symbol, "leverage": leverage}
    
    @router.post("/instruments/{symbol}/trailing_stop")
    async def set_trailing_stop(symbol: str, enabled: bool):
        """Enable/disable trailing stop for an instrument."""
        if symbol not in INSTRUMENTS:
            return {"error": f"Unknown instrument: {symbol}"}
        INSTRUMENTS[symbol]["trailing_stop"] = enabled
        log_event_func(f"[SETTINGS] {symbol} trailing stop {'enabled' if enabled else 'disabled'}", "event")
        return {"symbol": symbol, "trailing_stop": enabled}
    
    # =========================================================================
    # Quote endpoint - extracted from main.py
    # =========================================================================
    @router.get("/quote/{symbol}")
    async def get_quote(symbol: str):
        """Get real-time quote for a symbol."""
        async_client = get_async_client_func()
        quote = await async_client.get_quote(symbol)
        return quote if quote else {"error": f"Failed to fetch quote for {symbol}"}
    
    # =========================================================================
    # Chart endpoint - extracted from main.py
    # =========================================================================
    @router.get("/chart/{symbol}")
    @async_timed_func("get_chart_data")
    async def get_chart_data(symbol: str, resolution: str = "60", count: int = 100):
        """
        Get historical chart data for a symbol.
        FAST: Uses DB/cache first, only fetches fresh data if stale.
        """
        alpha_client = get_alpha_vantage_client_func()
        
        WARMUP = 60  # extra candles for SMA50 + MACD warmup
        fetch_count = count + WARMUP

        def _format_candles(candles):
            chart_data = []
            for candle in candles:
                timestamp = candle.get("timestamp", "")
                time_str = candle.get("time", "")
                if not time_str and timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        time_str = dt.strftime("%m/%d") if resolution == "D" else dt.strftime("%H:%M")
                    except Exception:
                        time_str = timestamp[:5] if len(timestamp) >= 5 else timestamp
                chart_data.append({
                    "time": time_str,
                    "timestamp": timestamp,
                    "close": round(candle["close"], 2),
                    "open": round(candle["open"], 2),
                    "high": round(candle["high"], 2),
                    "low": round(candle["low"], 2),
                    "volume": candle.get("volume", 0),
                })
            return chart_data

        # 1. FAST PATH: Check DB/cache first
        candle_map = {}
        db_candles = await async_load_candle_history_func(symbol, resolution, limit=fetch_count * 2)
        for c in db_candles:
            ts = c.get("timestamp", "")
            if ts:
                candle_map[ts] = c

        # Check if cache is fresh
        cache_is_fresh = False
        if db_candles:
            latest_ts = db_candles[-1].get("timestamp", "")
            if latest_ts:
                try:
                    latest_dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
                    cache_age = (now_warsaw_func() - latest_dt).total_seconds()
                    cache_is_fresh = cache_age < 300
                except:
                    pass

        fresh_candles = []
        source = "db" if candle_map else "none"

        # 2. Only fetch fresh data if cache is stale
        if not cache_is_fresh or len(candle_map) < 20:
            try:
                candles = await asyncio.wait_for(
                    asyncio.to_thread(alpha_client.get_candles, symbol, resolution, fetch_count),
                    timeout=3.0,
                )
                if candles and len(candles) > 0:
                    fresh_candles = candles
                    source = "alpha"
                    
                    # Store in DB
                    asyncio.create_task(_store_candles_async(symbol, resolution, candles))
            except asyncio.TimeoutError:
                source = "timeout"
            except Exception as e:
                source = f"error: {e}"

        # 3. Merge DB + fresh data
        all_candles = list(candle_map.values())
        for c in fresh_candles:
            ts = c.get("timestamp", "")
            if ts not in candle_map:
                all_candles.append(c)

        # 4. Sort and trim
        all_candles.sort(key=lambda x: x.get("timestamp", ""))
        all_candles = all_candles[-count:]
        
        chart_data = _format_candles(all_candles)
        
        return {
            "symbol": symbol,
            "resolution": resolution,
            "count": len(chart_data),
            "source": source,
            "chart": chart_data,
        }

    async def _store_candles_async(symbol, resolution, candles):
        """Store candles in DB (async wrapper)."""
        try:
            db_ref = db_module.get_db()
            for c in candles:
                db_ref.candles.update_one(
                    {"symbol": symbol.upper(), "resolution": resolution, "timestamp": c.get("timestamp", "")},
                    {"$set": c},
                    upsert=True,
                )
        except Exception:
            pass  # Non-critical
    
    # =========================================================================
    # Candles stats endpoint - extracted from main.py
    # =========================================================================
    @router.get("/candles/stats")
    async def get_candle_stats():
        """Get stored candle history statistics for all instruments."""
        stats = {}
        resolutions = ["1", "5", "15", "30", "60", "D"]
        for symbol in INSTRUMENTS:
            symbol_stats = {}
            for res in resolutions:
                cnt = await async_count_candles_func(symbol, res)
                if cnt > 0:
                    date_range = await async_get_candle_date_range_func(symbol, res)
                    symbol_stats[res] = {"count": cnt, "range": date_range}
            if symbol_stats:
                stats[symbol] = symbol_stats
        return {"stats": stats}
    
    # =========================================================================
    # Candles history endpoint - extracted from main.py
    # =========================================================================
    @router.get("/candles/{symbol}")
    @async_timed_func("get_candle_history")
    async def get_candle_history(
        symbol: str,
        resolution: str = "60",
        count: int = Query(100, ge=1, le=5000),
        start: Optional[str] = None,
        end: Optional[str] = None,
    ):
        """Get stored candle history for a symbol."""
        candles = await async_load_candle_history_func(symbol, resolution, start=start, end=end, limit=count)

        # Try aggregation from smaller intervals if not enough data
        if len(candles) < min(10, count):
            source_candidates = {
                "5": ["1"],
                "15": ["5", "1"],
                "30": ["15", "5", "1"],
                "60": ["30", "15", "5", "1"],
                "240": ["60", "30", "15"],
                "D": ["60", "30", "15", "5", "1"],
            }
            for src_res in source_candidates.get(resolution, []):
                stored = await async_load_candle_history_func(symbol, src_res, start=start, end=end)
                if stored and len(stored) >= 2:
                    aggregated = db_module.aggregate_candles(stored, resolution)
                    if len(aggregated) > len(candles):
                        candles = aggregated[-count:]
                        break

        return {
            "symbol": symbol,
            "resolution": resolution,
            "count": len(candles),
            "candles": candles,
        }
    
    # =========================================================================
    # Delete candles endpoint - extracted from main.py
    # =========================================================================
    @router.delete("/candles/{symbol}")
    async def delete_candles(
        symbol: str,
        resolution: str = Query("60", description="Resolution: 1, 5, 15, 30, 60, D"),
    ):
        """Delete cached candles for a symbol (to force fresh fetch)"""
        db_ref = db_module.get_db()
        
        result = db_ref.candles.delete_many({
            "symbol": symbol.upper(),
            "resolution": resolution,
        })
        
        return {"deleted": result.deleted_count, "symbol": symbol.upper(), "resolution": resolution}
    
    return router
