"""
CFD Trading Bot - FastAPI Backend
Real-time signal generation using Finnhub data and technical indicators
Simulated trading engine with USD currency
"""
print("[MAIN.PY] Loaded successfully")

import asyncio
import json
import os
import uuid
import signal
import sys
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from services.trading_engine import auto_trade_loop
from services.market_data import price_cache_loop
from services.state import broker, account, open_positions, closed_positions, INSTRUMENTS, INITIAL_BALANCE_USD, get_symbol_strategy
import uvicorn

# =============================================================================
# SIGNAL HANDLERS - Debug why process exits
# =============================================================================
# Load env vars BEFORE importing modules that need them
from dotenv import load_dotenv
load_dotenv()

# Use signal handler from utils
from utils.signal import create_signal_handler
_signal_handler = create_signal_handler()

from database import async_load_open_positions, async_sync_account_from_closed_trades
from fastapi import Body, FastAPI, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from timezone import WARSAW_TZ, now_warsaw

import functools

# =============================================================================
# TIMING PROFILER - Performance monitoring
# =============================================================================
import time
from typing import Any, Callable

import database as db
from alpha_vantage import get_async_client
from alpha_vantage import get_client as get_alpha_vantage_client
from alpha_vantage_news import get_client as get_news_client
from database import (
    async_count_candles,
    async_count_closed_positions,
    async_get_candle_date_range,
    async_load_account,
    async_load_candle_history,
    async_load_candles,
    async_load_closed_positions,
    async_load_event_log,
    async_load_open_positions,
    async_load_signal_cache_db,
    async_save_account,
    async_save_candles,
    async_save_event_log,
    async_save_signal_cache_db,
    async_save_trade,
    async_store_candles,
    get_setting,
)
from imessage_alerts import AlertConfig, get_dispatcher, iMessageAlertDispatcher
from indicators import TechnicalIndicators
from models import Component, ComponentType, Signal, SignalDirection, SignalResponse
from openclaw_integration import format_imessage_for_cfd_alert, set_openclaw_message_function
from settings import (
    ACCOUNT_REFRESH_SEC,
    LOGS_REFRESH_SEC,
    NEWS_REFRESH_INTERVAL_SEC,
    PRICE_CACHE_REFRESH_SEC,
    SIGNAL_SCAN_INTERVAL_SEC,
    get_all_settings,
    get_current_broker_settings,
)

from timeframes import TimeFrame, DEFAULT_TIMEFRAME
from strategy import load_strategies_from_file

# Use timing stats from services.state
from services.state import _timing_stats



# Timing decorators - NOW IMPORTED FROM utils.decorators
from utils.decorators import async_timed, sync_timed
from app.logging import log_event


# =============================================================================
# LIFESPAN HANDLER - Startup/Shutdown events (replaces deprecated @app.on_event)
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    global _trading_task, alpha_client

    # STARTUP
    log_event("[CFD TRADING BOT v0.2.0 - USD SIMULATION]", "event")
    log_event("Instruments: XAU (Gold), XAG (Silver), US100 (Nasdaq), BTC (Bitcoin)", "info")

    if not os.getenv("DASHBOARD_TOKEN"):
        log_event(
            "[AUTH] DASHBOARD_TOKEN is not set - API AUTH IS DISABLED. "
            "Set DASHBOARD_TOKEN in the environment to protect /api routes.",
            "warning",
        )

    # Database status
    if db.is_connected():
        log_event("MongoDB connected - trades & account persisted", "success")
        log_event(f"Restored {len(open_positions)} open positions, {len(closed_positions)} closed trades", "info")
        
        # Load settings from MongoDB on startup
        from services.state import set_auto_trade_enabled, set_auto_trade_interval, load_strategy_selections_from_db
        
        db_settings = db.list_settings()
        auto_trade_val = db_settings.get("AUTO_TRADE_ENABLED", 0)
        set_auto_trade_enabled(bool(auto_trade_val))
        log_event(f"Loaded AUTO_TRADE_ENABLED={auto_trade_val} from MongoDB", "info")
        
        interval = db_settings.get("AUTO_TRADE_INTERVAL_SEC", 30)
        set_auto_trade_interval(int(interval))
        log_event(f"Loaded AUTO_TRADE_INTERVAL_SEC={interval} from MongoDB", "info")
        
        # Load strategy selections from MongoDB
        load_strategy_selections_from_db()
        log_event("Loaded strategy selections from MongoDB", "info")
        
        db.ensure_candle_indexes()
        log_event("Candle history indexes ensured", "info")
        db.ensure_settings_indexes()
        log_event("Settings indexes ensured & defaults migrated", "info")
        db.ensure_trades_indexes()
        log_event("Trades indexes ensured", "info")
        db.ensure_news_indexes()
        log_event("News indexes ensured (TTL: 60 days)", "info")
        db.ensure_strategy_indexes()
        log_event("Strategy indexes ensured", "info")
        
        # Sync strategies from JSON to DB on startup
        db.sync_strategies_from_json()
        log_event("Strategies synced from JSON to DB", "info")
        
        db.list_settings()  # triggers migration of defaults
        await async_sync_account_from_closed_trades()
    else:
        log_event("MongoDB not configured - using in-memory storage (set MONGO_URI)", "warning")

    alpha_client = get_alpha_vantage_client()
    if alpha_client:
        log_event("Connected to Alpha Vantage API", "success")
    await async_load_signal_cache_db()
    try:
        # Don't block startup with news client - it's not critical
        # get_news_client()  # Disabled to prevent blocking on rate limits
        log_event("News client skipped (using mock data)", "info")
    except Exception as e:
        log_event(f"Failed to initialize news client: {e}", "error")
    # Update global account in services.state
    from services.state import account as state_account
    state_account.update(account)
    account["last_scan"] = datetime.utcnow().isoformat()
    log_event(f"Account loaded: ${account['balance_usd']:.2f} USD", "success")

    # Start autonomous trading loop with watchdog
    _trading_task = None
    
    async def start_auto_trade_with_watchdog():
        """Start auto-trade loop with automatic restart if it crashes or exits."""
        from services.trading_engine import auto_trade_loop
        while True:
            try:
                log_event("[AUTO-TRADE-WATCHDOG] Starting auto-trade loop...", "info")
                await auto_trade_loop()
                # If we get here, loop exited unexpectedly - log it!
                log_event("[AUTO-TRADE-WATCHDOG] Loop exited unexpectedly! Restarting...", "error")
            except Exception as e:
                import traceback
                log_event(f"[AUTO-TRADE-WATCHDOG] Loop crashed: {e}", "error")
                log_event(f"[AUTO-TRADE-WATCHDOG] Traceback: {traceback.format_exc()}", "error")
            finally:
                # Always wait before restart
                log_event("[AUTO-TRADE-WATCHDOG] Waiting 5s before restart...", "info")
                await asyncio.sleep(5)
    
    _trading_task = asyncio.create_task(start_auto_trade_with_watchdog())
    _price_cache_task = asyncio.create_task(price_cache_loop())
    log_event("[AUTO-TRADE] Background task launched (5 min interval)", "success")
    log_event("[PRICE-CACHE] Live price cache started (3 sec refresh)", "success")

    # Start strategy sync background task (every 5 minutes)
    async def strategy_sync_loop():
        """Periodically sync strategies from JSON to DB."""
        while True:
            await asyncio.sleep(300)  # 5 minutes
            try:
                db.sync_strategies_from_json()
                # Reload JSON strategies in memory
                from services.strategy_manager import get_strategy_manager as _gsm
                _gsm(force_reload=True)
                log_event("[STRATEGY-SYNC] Synced from JSON to DB", "info")
            except Exception as e:
                log_event(f"[STRATEGY-SYNC] Error: {e}", "error")
    
    _strategy_sync_task = asyncio.create_task(strategy_sync_loop())
    log_event("[STRATEGY-SYNC] Background sync started (5 min interval)", "success")

    # Daily digest notification (21:00 local by default, DIGEST_HOUR env)
    from services.digest import daily_digest_loop
    _digest_task = asyncio.create_task(daily_digest_loop())

    yield  # App runs here

    # SHUTDOWN
    if _trading_task:
        _trading_task.cancel()
        try:
            await _trading_task
        except asyncio.CancelledError:
            pass
    if _price_cache_task:
        _price_cache_task.cancel()
        try:
            await _price_cache_task
        except asyncio.CancelledError:
            pass
    if _strategy_sync_task:
        _strategy_sync_task.cancel()
        try:
            await _strategy_sync_task
        except asyncio.CancelledError:
            pass
    if _digest_task:
        _digest_task.cancel()
        try:
            await _digest_task
        except asyncio.CancelledError:
            pass
    await async_save_account(account)
    await async_save_event_log(event_log)
    # Skip news client cleanup - it's not critical
    # try:
    #     news_client = get_news_client()
    #     if hasattr(news_client, "close"):
    #         await news_client.close()
    # except Exception:
    #     pass
    log_event("[CFD TRADING BOT] Shutdown complete - state saved", "event")


# =============================================================================

app = FastAPI(
    title="CFD Trading Bot API",
    description="Real-time trading signals for CFD instruments with simulated trading",
    version="0.2.0",
    lifespan=lifespan,
)

from services.auth import auth_middleware, is_authorized

# Auth middleware registered FIRST so CORS (added after) wraps it as the
# outermost layer - Starlette runs later-added middleware first. This way
# 401 responses still carry CORS headers and the browser can read them.
app.middleware("http")(auth_middleware)

# CORS configuration (must stay OUTERMOST - keep this after the auth middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/auth/check")
async def auth_check():
    """Reachable only when authorized (or auth disabled). The frontend token gate probes this."""
    return {"ok": True}


from app import PLN_USD_RATE, event_log
from services import is_market_open, get_market_hours, update_live_price_cache, get_live_price
from services.state import _live_price_cache, _live_price_cache_last_update, get_signal_history_cache as _get_signal_history_cache, set_signal_history_cache as _set_signal_history_cache
from services.market_data import get_cached_quote, get_cached_candles
from services.strategy_manager import get_strategy_manager, analyze_with_new_strategy
from api.router import router as api_router

# Global state

# Include API routes from router (includes backtest optimization routes)
app.include_router(api_router)

# Enable Dynamic Positions feature
try:
    broker.enable_dynamic_exit(True, decay_threshold=0.25)  # Close if signal drops 25%
    try:
        log_event("[DYNAMIC-POSITIONS] Enabled with 25% decay threshold", "info")
    except:
        print("[DYNAMIC-POSITIONS] Enabled with 25% decay threshold")
except Exception as e:
    try:
        log_event(f"[DYNAMIC-POSITIONS] Not available: {e}", "warning")
    except:
        print(f"[DYNAMIC-POSITIONS] Not available: {e}")

# Convenience references (broker owns this state)
account = broker.get_account()
open_positions = broker.get_open_positions() if hasattr(broker, "open_positions") else []
closed_positions = broker.get_closed_positions() if hasattr(broker, "closed_positions") else []

# For SimulatedBroker, keep direct references to the same lists
if hasattr(broker, "open_positions"):
    open_positions = broker.open_positions
if hasattr(broker, "closed_positions"):
    closed_positions = broker.closed_positions
if hasattr(broker, "account"):
    account = broker.account

# Ensure all USD fields exist (migration for old accounts)
if "balance_usd" not in account:
    account["balance_usd"] = INITIAL_BALANCE_USD
if "equity_usd" not in account:
    account["equity_usd"] = account["balance_usd"]
if "available_usd" not in account:
    account["available_usd"] = account["balance_usd"]
if "used_margin" not in account:
    account["used_margin"] = 0.0
if "peak_balance_usd" not in account:
    account["peak_balance_usd"] = account["balance_usd"]
if "peak_equity_usd" not in account:
    account["peak_equity_usd"] = account["balance_usd"]

# Signal history cache for trend analysis - NOW DELEGATED TO services.state
# signal_history_cache = {}  # Removed - now uses get_signal_history_cache()

# Strategy selection per symbol (default: adaptive_regime)
# NOW DELEGATED TO services.state








# ============================================================
# Strategy Management Endpoints
# ============================================================

@app.get("/api/strategies/list")
async def list_strategies_api():
    """List all strategies from database."""
    from database import list_strategies_db
    strategies = list_strategies_db()
    return {"strategies": strategies, "count": len(strategies)}


@app.get("/api/strategies/{strategy_id}")
async def get_strategy_api(strategy_id: str):
    """Get a specific strategy from database."""
    from database import get_strategy_from_db
    strategy = get_strategy_from_db(strategy_id)
    if strategy:
        return strategy
    return {"error": f"Strategy {strategy_id} not found"}, 404


@app.post("/api/strategies/sync")
async def sync_strategies_api():
    """Sync strategies from JSON file to database."""
    from database import sync_strategies_from_json
    result = sync_strategies_from_json()
    # Reload JSON strategies in memory
    get_strategy_manager(force_reload=True)
    return result


@app.post("/api/strategies/reload")
async def reload_strategies_api():
    """Reload JSON strategies into memory."""
    manager = get_strategy_manager(force_reload=True)
    count = len(manager.strategies) if manager else 0
    return {"status": "success", "count": count}


@app.put("/api/strategies/{strategy_id}")
async def update_strategy_api(strategy_id: str, config: dict):
    """Update a strategy in database."""
    from database import save_strategy
    config["id"] = strategy_id
    save_strategy(config, updated_by="api")
    # Reload JSON strategies in memory
    get_strategy_manager(force_reload=True)
    return {"status": "success"}


@app.delete("/api/strategies/{strategy_id}")
async def delete_strategy_api(strategy_id: str):
    """Delete a strategy from database."""
    from database import delete_strategy_from_db
    result = delete_strategy_from_db(strategy_id)
    # Reload JSON strategies in memory
    get_strategy_manager(force_reload=True)
    return {"status": "success" if result else "not_found"}


# ============================================================
# Backtest endpoint - thin wrapper over backtest.engine.run_backtest
# ============================================================

@app.get("/api/backtest")
async def api_backtest(symbol: str, days: int = 14, strategy_id: str = None):
    """Run a backtest for a symbol using its configured JSON strategy."""
    from fastapi.responses import JSONResponse

    try:
        from api.routes.backtest import fetch_candles_for_config
        from backtest.engine import run_backtest

        manager = get_strategy_manager()
        if not manager:
            return JSONResponse({"error": "No strategies loaded"}, status_code=400)

        strategy_config = None
        if strategy_id:
            sid = strategy_id.replace("JSON:", "")
            strategy = manager.strategies.get(sid)
            if strategy is not None:
                strategy_config = strategy.config
        else:
            sym = symbol.upper()
            candidates = [s for s in manager.strategies.values() if s.symbol.upper() == sym]
            chosen = next((s for s in candidates if s.enabled), None) or (candidates[0] if candidates else None)
            if chosen is not None:
                strategy_config = chosen.config

        if strategy_config is None:
            return JSONResponse(
                {"error": f"No strategy found (symbol={symbol}, strategy_id={strategy_id})"},
                status_code=400,
            )

        strategy_config = {**strategy_config, "symbol": symbol.upper()}

        # Fetch candles for the base timeframe plus any higher timeframes the strategy uses
        candles_by_tf = await asyncio.to_thread(
            fetch_candles_for_config, strategy_config, symbol.upper(), days
        )
        if not candles_by_tf:
            return JSONResponse({"error": f"No candles available for {symbol}"}, status_code=400)

        report = await asyncio.to_thread(run_backtest, strategy_config, candles_by_tf)
        return {"report": report.to_doc()}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# =====================
# SERVE FRONTEND (production)
# =====================
# In production, the backend serves the built frontend as static files.
# Build with: cd frontend && npm run build
# The dist/ folder is served at / and all non-API routes fall back to index.html (SPA)

import pathlib

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_frontend_dist = pathlib.Path(__file__).parent.parent / "frontend" / "dist"

if _frontend_dist.is_dir():

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend SPA - all non-API routes get index.html"""
        # Skip API routes - let them 404
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Not found"}, status_code=404)
        file_path = _frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_frontend_dist / "index.html")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8001")))
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)

