"""
CFD Trading Bot - FastAPI Backend
Real-time signal generation using Finnhub data and technical indicators
Simulated trading engine with USD currency
"""

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

import uvicorn

# =============================================================================
# SIGNAL HANDLERS - Debug why process exits
# =============================================================================
# Use signal handler from utils
from utils.signal import create_signal_handler
_signal_handler = create_signal_handler()

from database import async_sync_account_from_closed_trades
from dotenv import load_dotenv
from fastapi import Body, FastAPI, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from timezone import WARSAW_TZ, now_warsaw

# Load env vars BEFORE importing modules that need them
load_dotenv()

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
from broker_factory import create_broker, create_data_provider
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

# Legacy function for backward compatibility
def get_strategy(strategy_id: str):
    """Legacy function - use StrategyManager instead."""
    manager = get_strategy_manager()
    return manager.strategies.get(strategy_id)

from timeframes import TimeFrame, DEFAULT_TIMEFRAME
from strategy import load_strategies_from_file
from strategies import list_strategies as old_list_strategies, mms_on_trade_result

# Use timing stats from services.state
from services.state import _timing_stats

INITIAL_BALANCE_USD = db.get_setting("INITIAL_BALANCE_USD", 3000.0)  # DB-driven!


# Timing decorators - NOW IMPORTED FROM utils.decorators
from utils.decorators import async_timed, sync_timed


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

    # Database status
    if db.is_connected():
        log_event("MongoDB connected - trades & account persisted", "success")
        log_event(f"Restored {len(open_positions)} open positions, {len(closed_positions)} closed trades", "info")
        db.ensure_candle_indexes()
        log_event("Candle history indexes ensured", "info")
        db.ensure_settings_indexes()
        log_event("Settings indexes ensured & defaults migrated", "info")
        db.ensure_trades_indexes()
        log_event("Trades indexes ensured", "info")
        db.list_settings()  # triggers migration of defaults
        await sync_account_from_closed_trades()
    else:
        log_event("MongoDB not configured - using in-memory storage (set MONGO_URI)", "warning")

    alpha_client = get_alpha_vantage_client()
    if alpha_client:
        log_event("Connected to Alpha Vantage API", "success")
    load_signal_cache()
    try:
        get_news_client()
        log_event("Web scraping news client initialized", "success")
    except Exception as e:
        log_event(f"Failed to initialize news client: {e}", "error")
    account["last_scan"] = datetime.utcnow().isoformat()
    log_event(f"Account loaded: ${account['balance_usd']:.2f} USD", "success")

    # Start autonomous trading loop
    _trading_task = asyncio.create_task(auto_trade_loop())
    _price_cache_task = asyncio.create_task(price_cache_loop())
    log_event("[AUTO-TRADE] Background task launched (5 min interval)", "success")
    log_event("[PRICE-CACHE] Live price cache started (3 sec refresh)", "success")

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
    await async_save_account(account)
    await async_save_event_log(event_log)
    try:
        news_client = get_news_client()
        if hasattr(news_client, "close"):
            await news_client.close()
    except Exception:
        pass
    log_event("[CFD TRADING BOT] Shutdown complete - state saved", "event")


# =============================================================================

app = FastAPI(
    title="CFD Trading Bot API",
    description="Real-time trading signals for CFD instruments with simulated trading",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app import PLN_USD_RATE, event_log
from services import is_market_open, get_market_hours, update_live_price_cache, get_live_price
from services.state import _live_price_cache, _live_price_cache_last_update, get_signal_history_cache as _get_signal_history_cache, set_signal_history_cache as _set_signal_history_cache
from services.market_data import get_cached_quote, get_cached_candles
from services.strategy_manager import get_strategy_manager, analyze_with_new_strategy
from api.router import router as api_router

# Global state

# Include API routes from router (includes backtest optimization routes)
app.include_router(api_router)

# Broker abstraction - switch via BROKER_TYPE env var ("sim" or "ibkr")
data_provider = create_data_provider()
broker = create_broker(data_provider)

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


def load_signal_cache():
    """Load signal history cache - DELEGATED TO SERVICE with DB fallback."""
    # First try to get from service
    cache = _get_signal_history_cache()
    if cache:
        log_event(f"Loaded signal cache from service ({len(cache)} symbols)")
        return cache
    # Try MongoDB if service cache is empty
    cached = db.load_signal_cache_db()
    if cached:
        _set_signal_history_cache(cached)
        log_event(f"Loaded signal cache from DB ({len(cached)} symbols)")
        return cached
    # Fallback to JSON file
    try:
        cache_file = "signal_cache.json"
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                cached = json.load(f)
            _set_signal_history_cache(cached)
            log_event(f"Loaded signal cache from file ({len(cached)} symbols)")
            return cached
    except Exception as e:
        log_event(f"Failed to load signal cache: {e}", "warning")
    return {}


# def save_signal_cache():
#     """Save signal history cache to DB + JSON file"""
#     db.save_signal_cache_db(signal_history_cache)
#     try:
#         cache_file = "signal_cache.json"
#         with open(cache_file, "w") as f:
#             json.dump(signal_history_cache, f)
#     except Exception:
#         pass  # File write is best-effort fallback


from app.config import INSTRUMENTS, get_instrument_config
from app.logging import log_event, event_log


# Live price cache - NOW IMPORTS FROM services.state
# Key: symbol, Value: {"price": float, "timestamp": float}
# PRICE_CACHE_REFRESH_SEC imported from settings.py


async def _update_live_price_cache():
    """Background task: keep live prices fresh for all instruments - DELEGATED TO SERVICE."""
    # Delegate to service
    await update_live_price_cache(data_provider, INSTRUMENTS)


# def get_live_price (moved to services)(symbol: str) -> Optional[float]:
    """Get cached live price for a symbol."""
    cached = _live_price_cache.get(symbol)
    if cached:
        return cached.get("price")
    return None



# def calculate_signal_score (moved to services)(indicators: dict, symbol: str = "") -> tuple[float, List[Component]]:
    """
    Multi-factor signal scoring with regime-adaptive weighting.
    Uses: RSI (corrected), MACD, Bollinger Bands, SMA trend, ADX trend strength,
    StochRSI for timing, and volume confirmation.

    In TRENDING markets (ADX > 25): momentum/trend components get higher weight.
    In RANGING markets (ADX < 20): mean-reversion components (BB, RSI) get higher weight.

    Returns score (-1 to +1) and components breakdown.
    """
    components = []
    scores = []
    weights = []

    # --- Detect market regime via ADX ---
    adx_data = indicators.get("adx")
    adx_value = adx_data["adx"] if adx_data else 20
    is_trending = adx_value > 25
    is_strong_trend = adx_value > 40
    regime = "TRENDING" if is_trending else "RANGING"

    if adx_data:
        trend_dir = "UP" if adx_data["plus_di"] > adx_data["minus_di"] else "DOWN"
        components.append(
            Component(
                type=ComponentType.TECHNICAL,
                name="ADX (Trend)",
                value=(
                    max(-1, min(1, (adx_value - 25) / 25))
                    if trend_dir == "UP"
                    else max(-1, min(1, -(adx_value - 25) / 25))
                ),
                description=f"ADX {adx_value:.0f} ({regime}, {trend_dir}) +DI:{adx_data['plus_di']:.0f} -DI:{adx_data['minus_di']:.0f}",
                confidence=0.8 if adx_value > 30 else 0.5,
                indicators=adx_data,
            )
        )

    # --- RSI Component (FIXED: oversold=BUY, overbought=SELL) ---
    if indicators.get("rsi_14") is not None:
        rsi = indicators["rsi_14"]
        # Correct interpretation: low RSI = oversold = buy opportunity
        if rsi < 30:
            rsi_score = (30 - rsi) / 30  # Oversold → positive (BUY)
        elif rsi > 70:
            rsi_score = -((rsi - 70) / 30)  # Overbought → negative (SELL)
        elif rsi < 45:
            rsi_score = (45 - rsi) / 45 * 0.3  # Mild bullish bias
        elif rsi > 55:
            rsi_score = -(rsi - 55) / 45 * 0.3  # Mild bearish bias
        else:
            rsi_score = 0  # Dead neutral zone

        rsi_score = max(-1, min(1, rsi_score))
        zone = "OVERSOLD" if rsi < 30 else "OVERBOUGHT" if rsi > 70 else "NEUTRAL"

        # v3 default: RSI weight = 0.35 (as per v3 weights)
        rsi_weight = 0.35

        components.append(
            Component(
                type=ComponentType.TECHNICAL,
                name="RSI (14)",
                value=rsi_score,
                description=f"RSI {rsi:.1f} ({zone})",
                confidence=0.85 if abs(rsi - 50) > 20 else 0.5,
                indicators={"value": rsi, "zone": zone},
            )
        )
        scores.append(rsi_score)
        weights.append(rsi_weight)

    # --- StochRSI Component (entry timing) ---
    stoch = indicators.get("stoch_rsi")
    if stoch:
        k, d = stoch["k"], stoch["d"]
        if k < 20:
            stoch_score = 0.6 + (20 - k) / 50  # Oversold → BUY
        elif k > 80:
            stoch_score = -(0.6 + (k - 80) / 50)  # Overbought → SELL
        else:
            stoch_score = 0

        # Crossover confirmation: %K crossing above %D = bullish
        if k > d and k < 30:
            stoch_score = max(stoch_score, 0.5)
        elif k < d and k > 70:
            stoch_score = min(stoch_score, -0.5)

        stoch_score = max(-1, min(1, stoch_score))
        if abs(stoch_score) > 0.1:
            components.append(
                Component(
                    type=ComponentType.TECHNICAL,
                    name="StochRSI",
                    value=stoch_score,
                    description=f"StochRSI K:{k:.0f} D:{d:.0f}",
                    confidence=0.7 if abs(k - 50) > 30 else 0.4,
                    indicators=stoch,
                )
            )
            scores.append(stoch_score)
            weights.append(0.10)

    # --- MACD Component (normalized by ATR for cross-symbol consistency) ---
    if indicators.get("macd"):
        macd = indicators["macd"]
        if macd.get("histogram") is not None and macd.get("macd_line") is not None:
            histogram = macd["histogram"]
            macd_line = macd["macd_line"]
            signal_line = macd.get("signal_line", 0) or 0
            atr = indicators.get("atr_14", 1) or 1

            # Normalize histogram by ATR for consistent scaling across symbols
            norm_hist = histogram / atr
            macd_score = max(-1, min(1, norm_hist * 2))

            cross = "BULLISH" if macd_line > signal_line else "BEARISH"
            # v3 default: MACD weight = 0.35 (as per v3 weights)
            macd_weight = 0.35

            components.append(
                Component(
                    type=ComponentType.TECHNICAL,
                    name="MACD",
                    value=macd_score,
                    description=f"MACD {cross} | hist/ATR: {norm_hist:.2f}",
                    confidence=0.8 if abs(norm_hist) > 0.5 else 0.5,
                    indicators=macd,
                )
            )
            scores.append(macd_score)
            weights.append(macd_weight)

    # --- Bollinger Bands Component (mean-reversion) ---
    if indicators.get("bollinger_bands"):
        bb = indicators["bollinger_bands"]
        closes = indicators.get("_closes", [])
        if closes:
            current_price = closes[-1]
            bb_upper = bb["upper"]
            bb_lower = bb["lower"]
            bb_range = bb_upper - bb_lower if bb_upper != bb_lower else 1

            bb_position = ((current_price - bb_lower) / bb_range) * 2 - 1
            bb_score = -bb_position * 0.8  # Near upper = sell, near lower = buy

            zone = "UPPER" if current_price > bb_upper else "LOWER" if current_price < bb_lower else "MIDDLE"
            # BB weight: higher in ranging markets
            bb_weight = 0.15 if is_trending else 0.25

            components.append(
                Component(
                    type=ComponentType.TECHNICAL,
                    name="Bollinger Bands",
                    value=max(-1, min(1, bb_score)),
                    description=f"BB {zone} (pos: {bb_position:.2f})",
                    confidence=0.75 if abs(bb_position) > 0.8 else 0.4,
                    indicators={"position": bb_position, "zone": zone},
                )
            )
            scores.append(max(-1, min(1, bb_score)))
            weights.append(bb_weight)

    # --- SMA Trend Component ---
    if indicators.get("sma_20") is not None and indicators.get("sma_50") is not None:
        sma_20 = indicators["sma_20"]
        sma_50 = indicators["sma_50"]
        if sma_50 > 0:
            sma_diff_pct = ((sma_20 - sma_50) / sma_50) * 100
            sma_score = max(-1, min(1, sma_diff_pct / 2))
            trend = "BULLISH" if sma_20 > sma_50 else "BEARISH"
            # SMA weight: higher in trending markets
            sma_weight = 0.20 if is_trending else 0.10

            components.append(
                Component(
                    type=ComponentType.TECHNICAL,
                    name="SMA Cross (20/50)",
                    value=sma_score,
                    description=f"SMA20/50: {sma_diff_pct:.2f}% ({trend})",
                    confidence=0.7,
                    indicators={"sma_20": sma_20, "sma_50": sma_50, "trend": trend},
                )
            )
            scores.append(sma_score)
            weights.append(sma_weight)

    # --- Volume Confirmation ---
    vol = indicators.get("volume_profile")
    if vol:
        vol_ratio = vol["vol_ratio"]
        up_down = vol["up_down_ratio"]

        # High volume confirms the move; low volume weakens it
        vol_multiplier = min(1.5, max(0.5, vol_ratio))
        vol_bias = max(-0.5, min(0.5, (up_down - 1.0) * 0.3))

        if vol_ratio > 1.5:
            components.append(
                Component(
                    type=ComponentType.TECHNICAL,
                    name="Volume",
                    value=vol_bias,
                    description=f"Vol {vol_ratio:.1f}x avg | Up/Down: {up_down:.1f}",
                    confidence=0.6,
                    indicators=vol,
                )
            )
            scores.append(vol_bias)
            weights.append(0.10)

    # --- Momentum (reduced weight, confirmation only) ---
    if indicators.get("momentum_10") is not None:
        momentum = indicators["momentum_10"]
        base_price = indicators.get("sma_20", 1) or 1
        mom_pct = (momentum / base_price) * 100 if base_price else 0
        momentum_score = max(-1, min(1, mom_pct / 2))

        components.append(
            Component(
                type=ComponentType.TECHNICAL,
                name="Momentum (10)",
                value=momentum_score,
                description=f"Momentum: {mom_pct:.2f}%",
                confidence=0.6,
                indicators={"value": momentum, "pct": mom_pct},
            )
        )
        scores.append(momentum_score)
        weights.append(0.20)  # v3 default: Momentum weight = 0.20

    # --- Candlestick Patterns ---
    cp = indicators.get("candlestick_patterns")
    if cp and cp.get("patterns") and abs(cp["net_bias"]) > 0.1:
        pattern_names = ", ".join(p["name"] for p in cp["patterns"])
        cp_score = max(-1, min(1, cp["net_bias"]))
        components.append(
            Component(
                type=ComponentType.TECHNICAL,
                name="Candlestick Patterns",
                value=cp_score,
                description=f"Patterns: {pattern_names} (bias: {cp['net_bias']:.2f})",
                confidence=0.7,
                indicators={"patterns": [p["name"] for p in cp["patterns"]], "net_bias": cp["net_bias"]},
            )
        )
        scores.append(cp_score)
        weights.append(0.15)

    # --- Calculate weighted composite score ---
    if scores:
        total_weight = sum(weights)
        composite_score = sum(s * w for s, w in zip(scores, weights)) / total_weight if total_weight > 0 else 0
    else:
        composite_score = 0

    # --- Component agreement bonus/penalty ---
    # If most components agree on direction, boost confidence; if mixed, dampen
    if len(scores) >= 3:
        bullish = sum(1 for s in scores if s > 0.1)
        bearish = sum(1 for s in scores if s < -0.1)
        agreement = max(bullish, bearish) / len(scores)
        if agreement > 0.7:
            composite_score *= 1.15  # Boost when components agree
        elif agreement < 0.4:
            composite_score *= 0.7  # Dampen when components disagree

    return max(-1, min(1, composite_score)), components


async def sync_account_from_closed_trades():
    """Fast sync using MongoDB aggregation - no full trade load."""
    stats = await async_sync_account_from_closed_trades()
    account.update(
        {
            "total_pnl_usd": stats["total_pnl_usd"],
            "win_count": stats["win_count"],
            "loss_count": stats["loss_count"],
            "win_rate": round(stats["win_count"] / stats["closed_trades"] * 100, 1) if stats["closed_trades"] else 0,
            "closed_trades": stats["closed_trades"],
        }
    )
    initial = db.get_setting("INITIAL_BALANCE_USD", 3000.0)
    account["balance_usd"] = initial + stats["total_pnl_usd"]
    await async_save_account(account)
    log_event(
        f"Account synced from closed trades: ${account['balance_usd']:.2f} (PnL ${stats['total_pnl_usd']:+.2f})", "info"
    )


# ── Risk Management ──────────────────────────────────────────────────
# Dynamic settings from DB (fallback to defaults)
# MAX_DRAWDOWN_PCT, MAX_OPEN_POSITIONS, MAX_RISK_PER_TRADE_PCT, INITIAL_BALANCE_USD


# def check_circuit_breaker (moved to services)() -> tuple[bool, str]:
    """Check if trading should be adjusted due to drawdown or position limits.

    Instead of blocking trading entirely when drawdown is high, we:
    - Increase minimum signal score requirement
    - Reduce position size
    - This allows recovery while managing risk
    """
    # Use equity (balance + unrealized P&L) for drawdown calculation
    current_equity = account.get("equity_usd", account["balance_usd"])
    initial_balance = db.get_setting("INITIAL_BALANCE_USD", 3000.0)
    peak_equity = max(initial_balance, account.get("peak_equity_usd", account.get("peak_balance_usd", initial_balance)))

    drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100 if peak_equity > 0 else 0
    max_dd_pct = db.get_setting("MAX_DRAWDOWN_PCT", 20.0)

    max_positions = db.get_setting("MAX_OPEN_POSITIONS", 3)
    if len(open_positions) >= max_positions:
        return False, f"Max {max_positions} positions reached"

    # If drawdown exceeds limit, still allow trading but with stricter conditions
    if drawdown_pct >= max_dd_pct:
        # Calculate risk multiplier based on drawdown severity
        # At 20% drawdown: 0.5x size, at 40%: 0.25x size
        severity = min((drawdown_pct - max_dd_pct) / 20.0, 1.0)  # 0 to 1
        size_multiplier = max(0.25, 1.0 - (severity * 0.75))  # 0.25 to 1.0

        # Increase min_score requirement (0.15 -> up to 0.45)
        min_score_boost = severity * 0.30  # up to +0.30

        log_event(
            f"[CIRCUIT-BREAKER] {drawdown_pct:.1f}% DD | Size: {size_multiplier:.0%} | Min score: +{min_score_boost:.2f}",
            "warning",
        )

        # Store in account for use in auto-trade
        account["_risk_multiplier"] = size_multiplier
        account["_min_score_boost"] = min_score_boost
        return True, f"RESTRICTED: {drawdown_pct:.1f}% drawdown"

    # Clear any previous restrictions
    account["_risk_multiplier"] = 1.0
    account["_min_score_boost"] = 0.0

    return True, "OK"


# def calculate_position_size (moved to services)(symbol: str, entry_price: float, stop_loss: float) -> float:
    """
    Calculate position size based on risk per trade and leverage.
    Risks MAX_RISK_PER_TRADE_PCT of account balance per trade.
    DYNAMIC RISK: risk is divided by number of open positions to keep total risk constant.
    """
    info = INSTRUMENTS.get(symbol, {})
    leverage = info.get("leverage", 1)

    # Get max risk per trade
    max_risk_pct = db.get_setting("MAX_RISK_PER_TRADE_PCT", 2.0)
    
    # Check if dynamic risk is enabled
    dynamic_risk = db.get_setting("DYNAMIC_RISK_ENABLED", 1)
    
    # Dynamic risk: divide by number of open positions to cap total risk
    # But ensure minimum risk of 0.5% per trade
    n_open = len([p for p in open_positions if p.get("status") == "open"])
    if dynamic_risk and n_open > 0:
        # Divide risk among open positions, but keep at least 0.5% per trade
        adjusted_risk_pct = max(0.5, max_risk_pct / n_open)
    else:
        adjusted_risk_pct = max_risk_pct
    
    risk_amount_usd = account["balance_usd"] * (adjusted_risk_pct / 100)

    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit <= 0:
        return info.get("lot_size", 0.01)

    # With leverage, P&L per unit = price_move * leverage
    # So size = risk_amount / (risk_per_unit * leverage) to keep actual loss = risk_amount
    size = risk_amount_usd / (risk_per_unit * leverage)

    # Clamp to instrument limits
    lot_size = info.get("lot_size", 0.01)
    min_size = lot_size
    max_size = lot_size * 10

    log_event(f"[RISK] {symbol}: {max_risk_pct}% base / {n_open} open = {adjusted_risk_pct:.2f}% effective risk", "debug")
    return round(max(min_size, min(size, max_size)), 4)


# async def update_account_equity():
#     """Update account equity based on open positions via broker."""
#     await broker._async_update_prices()
#     await sync_account_from_closed_trades()

# Semaphore to limit concurrent API calls
_api_semaphore = asyncio.Semaphore(4)

# Price cache to avoid repeated API calls
_price_cache: dict[str, tuple[float, float]] = {}  # symbol -> (price, timestamp)
_candles_cache: dict[str, tuple[list, float]] = {}  # symbol -> (candles, timestamp)
_CACHE_TTL = 60  # Cache for 60 seconds


async def _analyze_single_symbol(symbol: str, info: dict, news_client_instance) -> Signal:
    """Analyze a single symbol - runs in parallel for all symbols."""
    # Default timeframe for early returns
    timeframe = "5"
    
    try:
        # Use cached quote with 30s TTL
        async with _api_semaphore:
            quote = await asyncio.wait_for(get_cached_quote(symbol), timeout=5.0)

        # Get last known price from cache even if quote failed
        last_known_price = 0.0
        if symbol in _price_cache:
            last_known_price = _price_cache[symbol][0]

        if not quote:
            # Return neutral signal with last known price if available
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                score=0.0,
                confidence=0.0,
                technical_score=0.0,
                price_action_score=0.0,
                news_score=0.0,
                components=[],
                current_price=last_known_price,
                time_horizon=timeframe,
                entry_point=last_known_price,
                take_profit=0.0,
                stop_loss=0.0,
                risk_reward_ratio=0.0,
            )

        current_price = quote["price"]

        # Get timeframe from selected strategy (convert to db_resolution for compatibility)
        selected_strategy = get_symbol_strategy(symbol)
        
        # Use StrategyManager from JSON (supports timeframe)
        manager = get_strategy_manager()
        strategy_obj = manager.strategies.get(selected_strategy)
        if not strategy_obj:
            strategy_obj = manager.strategies.get('xau_v3_exp')
        
        # Handle both string and TimeFrame enum
        tf_value = strategy_obj.timeframe if strategy_obj and hasattr(strategy_obj, 'timeframe') else "5m"
        if hasattr(tf_value, 'value'):
            tf_value = tf_value.value
        
        # Convert to db_resolution (e.g., "5m" -> "5")
        try:
            tf_enum = TimeFrame(tf_value)
            timeframe = tf_enum.db_resolution
        except ValueError:
            timeframe = "5"  # fallback
        
        # Use cached candles with strategy's timeframe
        async with _api_semaphore:
            candles = await asyncio.wait_for(get_cached_candles(symbol, timeframe, 100, data_provider), timeout=10.0)
        if not candles or len(candles) < 20:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                score=0.0,
                confidence=0.0,
                technical_score=0.0,
                price_action_score=0.0,
                news_score=0.0,
                components=[],
                current_price=current_price,
                time_horizon=timeframe,
                entry_point=current_price,
                take_profit=0.0,
                stop_loss=0.0,
                risk_reward_ratio=0.0,
            )

        indicators = TechnicalIndicators.calculate_all(candles, period=14)
        if not indicators:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                score=0.0,
                confidence=0.0,
                technical_score=0.0,
                price_action_score=0.0,
                news_score=0.0,
                components=[],
                current_price=current_price,
                time_horizon=timeframe,
                entry_point=current_price,
                take_profit=0.0,
                stop_loss=0.0,
                risk_reward_ratio=0.0,
            )

        # Filter indicators based on per-symbol settings
        enabled_key = f"INDICATORS_{symbol}"
        enabled_indicators = db.get_setting(enabled_key)
        if enabled_indicators:
            # Map indicator names to their keys in the indicators dict
            indicator_map = {
                "RSI": ["rsi_14"],
                "MACD": ["macd", "macd_signal", "macd_hist"],
                "BB": ["bb_upper", "bb_lower", "bb_middle"],
                "SMA": ["sma_20", "sma_50", "sma_200"],
                "ADX": ["adx"],
                "STOCH": ["stoch_k", "stoch_d"],
                "MOMENTUM": ["momentum"],
                "WILLIAMS_R": ["williams_r"],
            }
            # Filter indicators dict to only include enabled ones
            filtered = {"_closes": indicators.get("_closes", [])}
            for ind_name in enabled_indicators:
                keys = indicator_map.get(ind_name, [])
                for key in keys:
                    if key in indicators:
                        filtered[key] = indicators[key]
            indicators = filtered

        indicators["_closes"] = [c["close"] for c in candles]

        # ── Multi-timeframe: fetch daily candles for higher-TF trend ──
        htf_bias = 0.0
        try:
            async with _api_semaphore:
                htf_candles = await asyncio.wait_for(get_cached_candles(symbol, "D", 60, data_provider), timeout=10.0)
            if htf_candles and len(htf_candles) >= 20:
                htf_ind = TechnicalIndicators.calculate_all(htf_candles, period=14)
                if htf_ind:
                    htf_sma20 = htf_ind.get("sma_20")
                    htf_sma50 = htf_ind.get("sma_50")
                    htf_adx = htf_ind.get("adx")
                    htf_price = htf_candles[-1]["close"]
                    if htf_sma20 and htf_sma50 and htf_sma50 > 0:
                        sma_diff = ((htf_sma20 - htf_sma50) / htf_sma50) * 100
                        htf_bias = max(-1, min(1, sma_diff / 3))
                    if htf_adx and htf_adx["adx"] > 30 and abs(htf_bias) > 0.1:
                        htf_bias *= 1.3
                        htf_bias = max(-1, min(1, htf_bias))
        except Exception:
            pass  # MTF is optional

        # ── VIX Filter (v2) ──
        # Get instrument-specific volatility index
        vix_data = None
        try:
            from historical_data import get_volatility_index

            vix_data = get_volatility_index(symbol)
            if vix_data:
                indicators["vix"] = vix_data
                print(
                    f"[VIX] {symbol}: {vix_data['value']} ({vix_data['name']}, change: {vix_data['change_pct']:+.1f}%)"
                )
            else:
                # Fallback to standard VIX
                vix_data = get_volatility_index("SPX")
                if vix_data:
                    indicators["vix"] = vix_data
        except Exception as e:
            print(f"[VIX] Could not fetch VIX for {symbol}: {e}")

        # ── Volatility filter ──
        # NOTE: Volatility check now handled by Strategy's filter config
        # The strategy.json defines volatility filter per-strategy
        atr = indicators.get("atr_14", current_price * 0.01)
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0

        # ── News sentiment (disabled to speed up - optional feature) ──
        news_score = 0.0
        # try:
        #     async with _api_semaphore:
        #         news = await asyncio.wait_for(
        #             news_client_instance.get_news(symbol, 5),
        #             timeout=1.0  # Quick timeout - don't wait for news
        #         )
        #     if news and len(news) > 0:
        #         sentiments = [article.get('sentiment', 0) for article in news]
        #         news_score = sum(sentiments) / len(sentiments) if sentiments else 0
        # except Exception:
        #     pass  # News is optional

        # ── Get selected strategy from DB ──
        selected_strategy = get_symbol_strategy(symbol)
        
        # ── Try JSON-based strategy (if selected or default) ──
        # If user selected a JSON strategy, use that one. Otherwise use any available JSON strategy for this symbol
        new_result = analyze_with_new_strategy(
            symbol, 
            candles, 
            current_price, 
            account.get("balance_usd", 3000),
            requested_strategy=selected_strategy if selected_strategy.startswith("JSON:") else None,
            atr_percent=atr_pct,
            vix_value=vix_data.get('value') if vix_data else None
        )
        
        if new_result:
            print(f"[STRATEGY] Using NEW JSON strategy for {symbol}: {new_result.get('strategy_id')}")
            # Clamp scores to valid range [-1, 1]
            json_score = max(-1.0, min(1.0, new_result["score"]))
            json_technical = max(-1.0, min(1.0, new_result["technical_score"]))
            return Signal(
                symbol=symbol,
                direction=SignalDirection.BUY if new_result["direction"] == "long" else SignalDirection.SELL,
                score=json_score,
                confidence=new_result["confidence"],
                technical_score=json_technical,
                price_action_score=0.0,
                news_score=0.0,
                components=new_result["components"],
                current_price=current_price,
                time_horizon=timeframe,
                entry_point=current_price,
                take_profit=new_result["take_profit"],
                stop_loss=new_result["stop_loss"],
                risk_reward_ratio=new_result["risk_reward_ratio"],
            )

        # ── Fallback: OLD strategy (DEPRECATED - see strategies.py) ──
        # ⚠️ DEPRECATED: Old strategy code - migrate to JSON-based strategies
        strategy_id = get_symbol_strategy(symbol)
        strategy = get_strategy(strategy_id)
        indicators["_closes"] = [c["close"] for c in candles]

        result = strategy.score(
            candles=candles,
            indicators=indicators,
            symbol=symbol,
            instrument_info=info,
            current_price=current_price,
            htf_bias=htf_bias,
            news_score=news_score,
        )

        # Clamp scores to valid range [-1, 1] - safety guard
        safe_score = max(-1.0, min(1.0, result["score"]))
        safe_technical = max(-1.0, min(1.0, result["technical_score"]))
        
        signal = Signal(
            symbol=symbol,
            direction=result["direction"],
            score=safe_score,
            confidence=result["confidence"],
            technical_score=safe_technical,
            price_action_score=0.0,
            news_score=news_score,
            components=result["components"],
            current_price=current_price,
            time_horizon=timeframe,
            entry_point=current_price,
            take_profit=result["take_profit"],
            stop_loss=result["stop_loss"],
            risk_reward_ratio=result["risk_reward_ratio"],
        )

        return signal

    except Exception as e:
        log_event(f"Error analyzing {symbol}: {e}", "error")
        return Signal(
            symbol=symbol,
            direction=SignalDirection.NEUTRAL,
            score=0.0,
            confidence=0.0,
            technical_score=0.0,
            price_action_score=0.0,
            news_score=0.0,
            components=[],
            current_price=0.0,
            time_horizon=timeframe,
            entry_point=0.0,
            take_profit=0.0,
            stop_loss=0.0,
            risk_reward_ratio=0.0,
        )


# generate_signals moved to services.trading_engine
from services.trading_engine import generate_signals


# =====================
# AUTO-TRADING ENGINE
# =====================

# Live price cache task
_price_cache_task = None


# price_cache_loop moved to services.market_data
from services.market_data import price_cache_loop


AUTO_TRADE_INTERVAL_SEC = 300  # Scan every 5 minutes
AUTO_TRADE_ENABLED = False  # Default: OFF until manually enabled  # Master switch - can be toggled via API (disabled until async-signals ready)
_trading_task = None  # Reference to the background task


async def auto_trade_loop():
    """
    Background loop that runs autonomously:
    1. Updates prices & checks TP/SL on open positions (auto-closes hits)
    2. Generates fresh signals for all instruments
    3. Opens trades automatically when signal is strong enough
    4. Persists account state to DB
    """
    global AUTO_TRADE_ENABLED

    # Wait a few seconds for startup to finish
    await asyncio.sleep(5)
    log_event("[AUTO-TRADE] Background trading loop started", "event")

    iteration_count = 0
    while True:
        iteration_count += 1
        try:
            print(f"[DEBUG AUTO-TRADE] Loop iteration #{iteration_count} at {datetime.utcnow().isoformat()}")
            if not AUTO_TRADE_ENABLED:
                await asyncio.sleep(AUTO_TRADE_INTERVAL_SEC)
                continue

            # ── Step 1: Update prices & auto-close TP/SL ──
            auto_closed = await broker._async_update_prices()
            if auto_closed:
                for closed in auto_closed:
                    pos = closed.get("position", {})
                    reason = closed.get("exit_reason", "TP/SL")
                    pnl = pos.get("pnl_usd", 0)
                    sym = pos.get("symbol", "?")
                    log_event(
                        f"[AUTO-CLOSE] {sym} {pos.get('direction', '').upper()} hit {reason} "
                        f"| P&L: {'+'if pnl>=0 else ''}{pnl:.2f} USD",
                        "success" if pnl >= 0 else "warning",
                    )
                await async_save_account(account)

            # ── Step 2: Generate fresh signals ──
            signals = await generate_signals()

            # Update signals cache for TP/SL reference
            global signals_cache
            signals_cache = {s.symbol: s for s in signals}

            # ── Step 3: Auto-execute trades on strong signals ──
            can_trade, reason = check_circuit_breaker()
            # Get risk adjustments from circuit breaker
            size_multiplier = account.get("_risk_multiplier", 1.0)
            min_score_boost = account.get("_min_score_boost", 0.0)

            if can_trade:
                # ── Step 2.5: Dynamic Positions - close weak profitable positions ──
                # Build current signals dict for dynamic exit check
                current_signals = {s.symbol: s.score for s in signals if s.direction not in (SignalDirection.NEUTRAL,)}
                positions_to_close = broker.check_dynamic_exit(current_signals)
                if positions_to_close:
                    log_event(f"[DYNAMIC-EXIT] Checking {len(positions_to_close)} positions for exit...", "info")
                    for pos_id in positions_to_close:
                        # Get fresh price for closing
                        pos = next((p for p in open_positions if p["id"] == pos_id), None)
                        if pos:
                            try:
                                quote = await data_provider.get_quote(pos["symbol"])
                                exit_price = quote.get("price") if quote else None
                            except:
                                exit_price = None
                            result = await broker.close_position(pos_id, exit_price=exit_price)
                            if "error" not in result:
                                pnl = result.get("position", {}).get("pnl_usd", 0)
                                log_event(f"[DYNAMIC-CLOSE] {pos['symbol']} | P&L: ${pnl:.2f} | Signal decayed", "info")
                            else:
                                log_event(f"[DYNAMIC-CLOSE] Failed: {result['error']}", "warning")
                    await async_save_account(account)

                for signal in signals:
                    if signal.direction in (SignalDirection.NEUTRAL,):
                        continue

                    sym = signal.symbol
                    info = INSTRUMENTS.get(sym, {})
                    min_score = info.get("min_score", 0.15) + min_score_boost

                    # Only auto-trade on signals that clear the threshold
                    if abs(signal.score) < min_score:
                        continue

                    # Determine trade direction
                    if signal.direction in (SignalDirection.BUY, SignalDirection.STRONG_BUY):
                        direction = "buy"
                    elif signal.direction in (SignalDirection.SELL, SignalDirection.STRONG_SELL):
                        direction = "sell"
                    else:
                        continue

                    # Skip if already have a position on this symbol in same direction
                    already_open = any(p["symbol"] == sym and p["direction"] == direction for p in open_positions)
                    if already_open:
                        continue

                    # Check if trading is enabled for this symbol
                    trade_enabled = db.get_setting(f"TRADE_ENABLED_{sym}", 1)
                    if not trade_enabled:
                        log_event(f"[AUTO-TRADE] Skipping {sym} - trading disabled", "info")
                        continue
                        continue

                    # Skip if market is closed for this symbol
                    if not is_market_open(sym):
                        log_event(f"[AUTO-TRADE] Skipping {sym} - market closed ({get_market_hours(sym)})", "info")
                        continue

                    # Check position limit BEFORE opening
                    max_positions = db.get_setting("MAX_OPEN_POSITIONS", 3)
                    if len(open_positions) >= max_positions:
                        log_event(f"[AUTO-TRADE] Skipping {sym} - max {max_positions} positions reached", "info")
                        continue

                    # Get CURRENT market price (not the signal's historical entry_point)
                    quote = await data_provider.get_quote(sym)
                    if not quote:
                        log_event(f"[AUTO-TRADE] Skipping {sym} - cannot get current price", "warning")
                        continue

                    entry_price = quote["price"]

                    # ALWAYS recalculate TP/SL from fresh ATR - signal values may be stale/invalid
                    # Get fresh candles for accurate ATR calculation
                    try:
                        fresh_candles = await get_cached_candles(sym, "60", 50, data_provider)
                        if fresh_candles and len(fresh_candles) >= 20:
                            ind = TechnicalIndicators.calculate_all(fresh_candles, period=14)
                            atr = ind.get("atr_14", entry_price * 0.01)
                        else:
                            atr = entry_price * 0.01
                    except Exception:
                        atr = entry_price * 0.01

                    if direction == "buy":
                        # TP above entry, SL below entry
                        take_profit = entry_price + (atr * 3)
                        stop_loss = entry_price - (atr * 2)
                    else:
                        # TP below entry, SL above entry
                        take_profit = entry_price - (atr * 3)
                        stop_loss = entry_price + (atr * 2)

                    size = calculate_position_size(sym, entry_price, stop_loss) * size_multiplier

                    result = await broker.open_position(
                        symbol=sym,
                        direction=direction,
                        size=size,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                        entry_price=entry_price,
                        signal_score=signal.score,
                    )
                    if "error" not in result:
                        log_event(
                            f"[AUTO-TRADE] Opened {direction.upper()} {sym} @ {entry_price:.2f} "
                            f"| Score: {signal.score:.3f} | SL: {stop_loss:.2f} TP: {take_profit:.2f}",
                            "success",
                        )
                    else:
                        log_event(f"[AUTO-TRADE] Failed to open {sym}: {result['error']}", "warning")
            else:
                log_event(f"[AUTO-TRADE] Skipping: {reason}", "info")

            # ── Step 4: Persist state ──
            await async_save_account(account)
            # Save signal cache via service
            _set_signal_history_cache(_get_signal_history_cache())
            await async_save_signal_cache_db(_get_signal_history_cache())

            log_event(
                f"[AUTO-TRADE] Scan complete | Balance: ${account['balance_usd']:.2f} USD "
                f"| Open: {len(open_positions)} | Closed: {len(closed_positions)}",
                "info",
            )

        except Exception as e:
            import traceback
            log_event(f"[AUTO-TRADE] Error in trading loop: {str(e)}", "error")
            log_event(f"[AUTO-TRADE] Traceback: {traceback.format_exc()}", "error")

        # Use shorter sleep intervals to avoid event loop issues
        sleep_cycles = AUTO_TRADE_INTERVAL_SEC // 60  # Sleep in 60s chunks
        remaining = AUTO_TRADE_INTERVAL_SEC % 60
        
        try:
            for i in range(sleep_cycles):
                log_event(f"[AUTO-TRADE] Sleep cycle {i+1}/{sleep_cycles} (60s)...", "info")
                await asyncio.sleep(60)
                log_event(f"[AUTO-TRADE] Sleep cycle {i+1} complete", "info")
            
            if remaining > 0:
                log_event(f"[AUTO-TRADE] Final sleep {remaining}s...", "info")
                await asyncio.sleep(remaining)
            
            log_event(f"[AUTO-TRADE] Wake up from full sleep cycle, iteration #{iteration_count}", "info")
        except Exception as e:
            log_event(f"[AUTO-TRADE] Error in sleep: {str(e)}", "error")
            log_event(f"[AUTO-TRADE] Will retry after 30s...", "info")
            await asyncio.sleep(30)  # Fallback sleep


# EXTRACTED TO api/routes/control.py - using router below
# @app.get("/api/auto-trade")
# async def get_auto_trade_status():
#     """Get auto-trading status."""
#     return {
#         "enabled": AUTO_TRADE_ENABLED,
#         "interval_sec": AUTO_TRADE_INTERVAL_SEC,
#         "last_scan": account.get("last_scan"),
#         "open_positions": len(open_positions),
#     }


# @app.post("/api/auto-trade")
# async def set_auto_trade(enabled: bool):
#     """Enable/disable auto-trading."""
#     global AUTO_TRADE_ENABLED
#     AUTO_TRADE_ENABLED = enabled
#     log_event(f"[AUTO-TRADE] {'ENABLED' if enabled else 'DISABLED'}", "event")
#     return {"enabled": AUTO_TRADE_ENABLED}


# @app.post("/api/auto-trade/interval")
# async def set_auto_trade_interval(seconds: int):
#     """Set auto-trade scan interval (min 60s, max 3600s)."""
#     global AUTO_TRADE_INTERVAL_SEC
#     if seconds < 60 or seconds > 3600:
#         return {"error": "Interval must be between 60 and 3600 seconds"}
#     AUTO_TRADE_INTERVAL_SEC = seconds
#     log_event(f"[AUTO-TRADE] Interval set to {seconds}s", "event")
#     return {"interval_sec": AUTO_TRADE_INTERVAL_SEC}


# EXTRACTED TO api/routes/root.py - using router below
# @app.get("/")
# async def root():
#     """Serve frontend or return API info"""
#     # Check if frontend dist exists, serve it
#     if _frontend_dist.is_dir():
#         return FileResponse(_frontend_dist / "index.html")
#     return {"message": "CFD Trading Bot API", "status": "running", "version": "0.2.0"}


# @app.get("/health")
# async def health():
#     """Health check with MongoDB status"""
#     mongo_status = "connected" if db.is_connected() else "disconnected"
#     return {"status": "ok", "timestamp": datetime.utcnow().isoformat(), "mongodb": mongo_status, "version": "0.2.0"}


# @app.get("/api/debug/positions")
# async def debug_positions():
#     """Debug endpoint to check all positions in memory vs DB."""
#     from database import load_closed_positions, load_open_positions

#     db_open = load_open_positions()
#     db_closed = load_closed_positions(20)
#     return {
#         "memory": {
#             "open_count": len(open_positions),
#             "open_ids": [p["id"] for p in open_positions],
#             "broker_open": [p["id"] for p in broker.get_open_positions()],
#         },
#         "database": {
#             "open_count": len(db_open),
#             "open_ids": [p["id"] for p in db_open],
#             "closed_count": len(db_closed),
#             "recent_closed": [
#                 (p["id"], p["symbol"], p["entry_price"], p.get("closed_at", "unknown")[:16]) for p in db_closed[:5]
#             ],
#         },
#     }


# EXTRACTED TO api/routes/status.py - using router below
# @app.get("/api/timing-report")
# async def get_timing_report():
#     """Get performance timing report for all profiled functions."""
#     report = {}
#     for name, stats in _timing_stats.items():
#         if stats["calls"] > 0:
#             report[name] = {
#                 "calls": stats["calls"],
#                 "total_sec": round(stats["total"], 3),
#                 "avg_sec": round(stats["total"] / stats["calls"], 3),
#                 "min_sec": round(stats["min"], 3),
#                 "max_sec": round(stats["max"], 3),
#             }
#     # Sort by total time (descending)
#     report = dict(sorted(report.items(), key=lambda x: -x[1]["total_sec"]))
#     return {"timestamp": datetime.utcnow().isoformat(), "functions": report, "count": len(report)}


# @app.delete("/api/timing-report")
# async def clear_timing_report():
#     """Clear timing statistics."""
#     _timing_stats.clear()
#     return {"status": "cleared"}


# @app.get("/api/status")
# async def get_status():
#     """Detailed status endpoint for debugging"""
#     mongo_uri_set = bool(os.getenv("MONGO_URI") or os.getenv("MONGODB_URI"))
#     mongo_connected = db.is_connected()

#     return {
#         "status": "ok",
#         "timestamp": datetime.utcnow().isoformat(),
#         "version": "0.2.0",
#         "environment": {
#             "mongo_uri_set": mongo_uri_set,
#             "mongo_db": os.getenv("MONGO_DB", "cfd_trading_bot"),
#             "mongo_connected": mongo_connected,
#             "broker_type": os.getenv("BROKER_TYPE", "sim"),
#         },
#         "account": {
#             "balance_usd": account.get("balance_usd", 0),
#             "equity_usd": account.get("equity_usd", 0),
#             "open_trades": len(open_positions),
#             "mode": account.get("mode", "simulate"),
#         },
#         "instruments": list(INSTRUMENTS.keys()),
#     }


# @app.get("/api/signals", response_model=SignalResponse)  # EXTRACTED to service














async def run_backtest(
    symbol: str = Query(..., description="Symbol to backtest"),
    resolution: str = Query("5", description="Resolution: 1, 5, 15, 30, 60, D"),
    days: int = Query(14, description="Number of days to backtest"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD), defaults to days ago"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD), defaults to today"),
    min_score: float = Query(0.15, description="Minimum score threshold"),
    initial_balance: float = Query(3000.0, description="Initial balance"),
    strategy: Optional[str] = Query(None, description="Strategy ID (adaptive_regime, mms)"),
    indicators: Optional[str] = Query(
        None, description="Comma-separated indicators (RSI,MACD,BB,SMA,ADX,STOCH,MOMENTUM)"
    ),
    settings: Optional[str] = Query(
        None, description="Settings (e.g., rsi_period=14,macd_fast=12)"
    ),
    leverage: int = Query(10, description="Leverage (e.g., 10 = 10x)"),
    tp_pct: float = Query(0.02, description="Take profit % (e.g., 0.02 = 2%)"),
    sl_pct: float = Query(0.01, description="Stop loss % (e.g., 0.01 = 1%)"),
    risk_pct: float = Query(0.01, description="Risk per trade % (e.g., 0.01 = 1%)"),
    trailing_sl_pct: float = Query(0.0, description="Trailing SL % (0 = disabled, e.g., 0.5 = move SL to breakeven at 0.5% profit)"),
    volume_filter: float = Query(0.0, description="Min volume as % of avg (0 = disabled, e.g., 0.5 = only trade if volume > 50% of avg)"),
    multi_tf: Optional[str] = Query(None, description="Multi-timeframe alignment (e.g., '15,30' - trade only if all timeframes agree)"),
    htf_rsi_filter: Optional[str] = Query(None, description="HTF RSI filter (e.g., '30' - check RSI on higher TF and skip if extreme)"),
    htf_adx_filter: Optional[str] = Query(None, description="HTF ADX filter (e.g., '30' - skip if ADX < 20 on higher TF)"),
    htf_resistance_filter: Optional[str] = Query(None, description="HTF resistance filter (e.g., '30' - reduce TP if price near HTF high/low)"),
    htf_vwap_filter: Optional[str] = Query(None, description="HTF VWAP filter (e.g., '60' - only trade when price moving toward VWAP)"),
    htf_trend_filter: Optional[str] = Query(None, description="HTF trend filter (e.g., '30' - only trade with HTF trend: RSI>50 long, RSI<50 short)"),
    adx_filter_mode: Optional[str] = Query(None, description="ADX filter: 'trend' (ADX>25 uses TP=5%) or 'chop' (ADX<20 uses TP=3%, SL=1.5%)"),
    divergence_filter: Optional[str] = Query(None, description="Divergence filter (e.g., 'RSI' or 'MACD' - check for bullish/bearish divergence)"),
    
    # Strategy weights (v3 defaults: MACD=0.35, RSI=0.35, Momentum=0.2)
    order_block_filter: Optional[str] = Query(None, description="Order Block filter (e.g., '1' - enable, check for order blocks)"),
    
    # Strategy weights
    rsi_weight: float = Query(None, description="RSI weight override (e.g., 0.2)"),
    macd_weight: float = Query(None, description="MACD weight override (e.g., 0.3)"),
    stoch_weight: float = Query(None, description="Stoch weight override (e.g., 0.1)"),
    momentum_weight: float = Query(None, description="Momentum weight override (e.g., 0.2)"),
    adx_weight: float = Query(None, description="ADX weight override (e.g., 0.15)"),
    bb_weight: float = Query(None, description="Bollinger Bands weight override (e.g., 0.15)"),
):
    """
    Run backtest on historical data.
    Returns all trades and performance metrics.

    If strategy/indicators not provided, uses per-symbol defaults from DB.
    """
    import time
    start_time = time.time()

    from database import get_db

    # Build strategy weights dict if any provided
    custom_weights = {}
    if rsi_weight is not None:
        custom_weights['rsi'] = rsi_weight
    if macd_weight is not None:
        custom_weights['macd'] = macd_weight
    if stoch_weight is not None:
        custom_weights['stoch'] = stoch_weight
    if momentum_weight is not None:
        custom_weights['momentum'] = momentum_weight
    if adx_weight is not None:
        custom_weights['adx'] = adx_weight
    if bb_weight is not None:
        custom_weights['bb'] = bb_weight

    # Get candles from DB
    symbol_key = symbol.upper()
    if symbol_key not in INSTRUMENTS:
        return {"error": f"Unknown symbol: {symbol}"}

    # Validate strategy if provided
    if strategy:
        from strategies import STRATEGIES

        if strategy not in STRATEGIES:
            return {"error": f"Unknown strategy: {strategy}. Available: {list(STRATEGIES.keys())}"}
        strategy_id = strategy
    else:
        strategy_id = get_symbol_strategy(symbol_key)

    from strategies import get_strategy
    strategy = get_strategy(strategy_id)
    instrument_info = INSTRUMENTS.get(symbol_key, {})

    # Parse custom settings if provided (e.g., "rsi_period=14,macd_fast=12")
    custom_settings = {}
    if settings:
        try:
            for pair in settings.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    custom_settings[k.strip()] = v.strip()
        except Exception:
            pass  # Ignore invalid settings

    # Apply custom settings to strategy
    if custom_settings:
        for ind in strategy.default_indicators:
            if hasattr(ind, "settings") and ind.settings:
                for key in list(ind.settings.keys()):
                    # Map frontend keys to settings keys
                    mapping = {
                        "rsi_period": "period",
                        "rsi_overbought": "overbought",
                        "rsi_oversold": "oversold",
                        "macd_fast": "fast",
                        "macd_slow": "slow",
                        "macd_signal": "signal",
                        "bb_period": "period",
                        "bb_std": "std",
                    }
                    frontend_key = f"{ind.id.lower()}_{key}"
                    if frontend_key in custom_settings:
                        try:
                            val = custom_settings[frontend_key]
                            # Try to convert to int/float
                            if "." in val:
                                ind.settings[key] = float(val)
                            else:
                                ind.settings[key] = int(val)
                        except Exception:
                            pass

    # Parse indicators if provided
    if indicators:
        enabled_indicators = [ind.strip().upper() for ind in indicators.split(",")]
    else:
        # Try to get from DB, otherwise use strategy defaults
        enabled_key = f"INDICATORS_{symbol_key}"
        db_indicators = get_setting(enabled_key)
        if db_indicators:
            enabled_indicators = db_indicators
        else:
            # Use all indicators from strategy
            enabled_indicators = strategy.get_enabled_indicators()

    # Get candles from DB
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days)
    
    # Override with specific dates if provided
    if date_from:
        try:
            start_dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
        except:
            pass
    if date_to:
        try:
            end_dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
        except:
            pass
    
    db = get_db()
    cursor = db.candles.find(
        {"symbol": symbol_key, "resolution": resolution, "timestamp": {"$gte": start_dt.isoformat()}}
    ).sort("timestamp", 1)

    candles = list(cursor)
    if not candles:
        return {"error": f"No candles found for {symbol_key} {resolution}"}

    if len(candles) < 50:
        return {"error": f"Not enough candles: {len(candles)}"}

    print(f"[BACKTEST] Processing {len(candles)} candles for {symbol_key} {resolution}")

    candles = [
        {
            "timestamp": c.get("timestamp"),
            "open": c.get("open"),
            "high": c.get("high"),
            "low": c.get("low"),
            "close": c.get("close"),
            "volume": c.get("volume"),
        }
        for c in candles
    ]

    # Run backtest
    balance = initial_balance
    peak_balance = initial_balance
    trades = []
    open_trade = None
    
    # Parse HTF RSI filter parameter
    htf_rsi_res = None
    htf_rsi_candles = []
    if htf_rsi_filter:
        htf_rsi_res = htf_rsi_filter.strip()
        tf_cursor = db.candles.find(
            {"symbol": symbol_key, "resolution": htf_rsi_res, "timestamp": {"$gte": start_dt.isoformat()}}
        ).sort("timestamp", 1)
        htf_rsi_candles = list(tf_cursor)
        if htf_rsi_candles:
            print(f"[BACKTEST] HTF RSI filter: {htf_rsi_res}, {len(htf_rsi_candles)} candles")
    
    # Parse HTF ADX filter parameter
    htf_adx_res = None
    htf_adx_candles = []
    if htf_adx_filter:
        htf_adx_res = htf_adx_filter.strip()
        tf_cursor = db.candles.find(
            {"symbol": symbol_key, "resolution": htf_adx_res, "timestamp": {"$gte": start_dt.isoformat()}}
        ).sort("timestamp", 1)
        htf_adx_candles = list(tf_cursor)
        if htf_adx_candles:
            print(f"[BACKTEST] HTF ADX filter: {htf_adx_res}, {len(htf_adx_candles)} candles")
    
    # Parse HTF resistance filter parameter
    htf_res_res = None
    htf_res_candles = []
    if htf_resistance_filter:
        htf_res_res = htf_resistance_filter.strip()
        tf_cursor = db.candles.find(
            {"symbol": symbol_key, "resolution": htf_res_res, "timestamp": {"$gte": start_dt.isoformat()}}
        ).sort("timestamp", 1)
        htf_res_candles = list(tf_cursor)
        if htf_res_candles:
            print(f"[BACKTEST] HTF Resistance filter: {htf_res_res}, {len(htf_res_candles)} candles")
    
    # Parse HTF VWAP filter parameter
    htf_vwap_res = None
    htf_vwap_candles = []
    if htf_vwap_filter:
        htf_vwap_res = htf_vwap_filter.strip()
        tf_cursor = db.candles.find(
            {"symbol": symbol_key, "resolution": htf_vwap_res, "timestamp": {"$gte": start_dt.isoformat()}}
        ).sort("timestamp", 1)
        htf_vwap_candles = list(tf_cursor)
        if htf_vwap_candles:
            print(f"[BACKTEST] HTF VWAP filter: {htf_vwap_res}, {len(htf_vwap_candles)} candles")
    
    # Parse HTF trend filter parameter (SIMPLE: RSI > 50 = long, RSI < 50 = short)
    htf_trend_res = None
    htf_trend_candles = []
    if htf_trend_filter:
        htf_trend_res = htf_trend_filter.strip()
        tf_cursor = db.candles.find(
            {"symbol": symbol_key, "resolution": htf_trend_res, "timestamp": {"$gte": start_dt.isoformat()}}
        ).sort("timestamp", 1)
        htf_trend_candles = list(tf_cursor)
        if htf_trend_candles:
            print(f"[BACKTEST] HTF Trend filter: {htf_trend_res}, {len(htf_trend_candles)} candles")
    
    # Parse multi-timeframe parameter
    multi_tf_resolutions = []
    multi_tf_candles = {}
    if multi_tf:
        multi_tf_resolutions = [r.strip() for r in multi_tf.split(',') if r.strip()]
        print(f"[BACKTEST] Multi-TF enabled: {multi_tf_resolutions}")
        
        # Get candles for additional timeframes from DB
        if multi_tf_resolutions:
            for tf_res in multi_tf_resolutions:
                tf_cursor = db.candles.find(
                    {"symbol": symbol_key, "resolution": tf_res, "timestamp": {"$gte": start_dt.isoformat()}}
                ).sort("timestamp", 1)
                tf_candles = list(tf_cursor)
                if tf_candles:
                    multi_tf_candles[tf_res] = [
                        {"timestamp": c.get("timestamp"), "close": c.get("close"), "volume": c.get("volume")}
                        for c in tf_candles
                    ]
                    print(f"[BACKTEST] Loaded {len(multi_tf_candles[tf_res])} candles for {tf_res}")

    # Calculate indicators and signals for each candle
    for i in range(50, len(candles)):  # Need 50 candles for warmup
        candle_window = candles[max(0, i - 50) : i]
        current_candle = candles[i]

        if len(candle_window) < 50:
            continue

        # Calculate indicators
        try:
            indicators = TechnicalIndicators.calculate_all(candle_window, period=14)
            current_price = current_candle.get("close", 0)
            if current_price <= 0:
                continue
        except Exception:
            continue

        # Use actual strategy to generate signal
        try:
            result = strategy.score(candle_window, indicators, symbol_key, instrument_info, current_price, custom_weights=custom_weights if custom_weights else None)
            score = result.get("score", 0)
            direction = result.get("direction")
            tp = result.get("take_profit")
            sl = result.get("stop_loss")
        except Exception as e:
            print(f"[BACKTEST] Error at candle {i}: {e}")
            continue

        # Debug: log score and direction every 50 candles
        if i % 50 == 0:
            print(f"[BACKTEST] candle {i}: score={score}, direction={direction}")

        # Use score to determine direction (more flexible than strategy's direction)
        direction_str = None
        if score >= min_score:
            direction_str = "buy"
        elif score <= -min_score:
            direction_str = "sell"

        # Check if score meets threshold and we don't have open trade
        if direction_str and open_trade is None:
            # Check volume filter if enabled
            if volume_filter > 0:
                try:
                    # Safety check: ensure candles is defined and has data
                    if 'candles' not in dir() or not candles or len(candles) < i:
                        raise ValueError(f"Candles not available or insufficient: len={len(candles) if 'candles' in dir() else 'N/A'}, i={i}")
                    
                    current_volume = current_candle.get("volume", 0)
                    if current_volume is None:
                        current_volume = 0
                    # Calculate average volume from last 20 candles
                    start_idx = max(0, i - 20)
                    volumes = []
                    for c in candles[start_idx:i]:
                        v = c.get("volume", 0)
                        if v is not None and v > 0:
                            volumes.append(v)
                    avg_volume = sum(volumes) / len(volumes) if volumes else 0
                    if avg_volume > 0 and current_volume < avg_volume * volume_filter:
                        direction_str = None  # Skip this signal due to low volume
                except Exception as e:
                    print(f"[BACKTEST] Volume filter error at i={i}: {e}")
                    # Don't fail the whole backtest - just skip filtering
            
            # Check multi-timeframe alignment if enabled
            if multi_tf_candles and direction_str:
                try:
                    # Get current timestamp
                    current_ts = current_candle.get("timestamp", "")
                    
                    # Check each additional timeframe
                    tf_agrees = True
                    for tf_res, tf_candles_list in multi_tf_candles.items():
                        if not tf_candles_list:
                            continue
                        
                        # Find closest candle in this timeframe
                        tf_direction = None
                        for j, tc in enumerate(tf_candles_list):
                            if tc.get("timestamp", "") >= current_ts:
                                if j > 0:
                                    prev = tf_candles_list[j-1]
                                    curr = tc
                                    # Simple direction check: compare close prices
                                    if curr.get("close", 0) > prev.get("close", 0):
                                        tf_direction = "buy"
                                    elif curr.get("close", 0) < prev.get("close", 0):
                                        tf_direction = "sell"
                                break
                        
                        # Check if this timeframe agrees
                        if tf_direction and tf_direction != direction_str:
                            tf_agrees = False
                            break
                    
                    if not tf_agrees:
                        direction_str = None  # Skip - timeframes don't agree
                        print(f"[BACKTEST] Multi-TF: Skipping {symbol_key} at i={i} - timeframes don't align")
                except Exception as e:
                    print(f"[BACKTEST] Multi-TF error: {e}")
            
            # HTF RSI Filter - skip trade if higher timeframe RSI is extreme
            if htf_rsi_candles and direction_str:
                try:
                    current_ts = current_candle.get("timestamp", "")
                    for j, tc in enumerate(htf_rsi_candles):
                        if tc.get("timestamp", "") >= current_ts:
                            if j > 0:
                                window = htf_rsi_candles[max(0, j-14):j]
                                if len(window) >= 14:
                                    closes = [c.get("close", 0) for c in window]
                                    if closes and all(c > 0 for c in closes):
                                        gains = []
                                        losses = []
                                        for k in range(1, len(closes)):
                                            diff = closes[k] - closes[k-1]
                                            if diff > 0:
                                                gains.append(diff)
                                            else:
                                                losses.append(abs(diff))
                                        avg_gain = sum(gains) / 14 if gains else 0
                                        avg_loss = sum(losses) / 14 if losses else 0
                                        rs = avg_gain / avg_loss if avg_loss > 0 else 100
                                        rsi = 100 - (100 / (1 + rs))
                                        
                                        # Skip if HTF RSI is extreme
                                        if (direction_str == "buy" and rsi > 70) or (direction_str == "sell" and rsi < 30):
                                            print(f"[BACKTEST] HTF RSI {rsi:.0f} extreme - SKIPPING trade")
                                            direction_str = None
                            break
                except Exception as e:
                    pass  # Continue on error
            
            # HTF ADX Filter - skip if no trend
            if htf_adx_candles and direction_str:
                try:
                    current_ts = current_candle.get("timestamp", "")
                    for j, tc in enumerate(htf_adx_candles):
                        if tc.get("timestamp", "") >= current_ts:
                            if j > 14:
                                window = htf_adx_candles[j-14:j]
                                highs = [c.get("high", 0) for c in window]
                                lows = [c.get("low", 0) for c in window]
                                closes = [c.get("close", 0) for c in window]
                                
                                if highs and lows and closes and all(h > 0 and l > 0 and c > 0 for h,l,c in zip(highs, lows, closes)):
                                    plus_dm = []
                                    minus_dm = []
                                    for k in range(1, len(window)):
                                        high_diff = highs[k] - highs[k-1]
                                        low_diff = lows[k-1] - lows[k]
                                        if high_diff > low_diff and high_diff > 0:
                                            plus_dm.append(high_diff)
                                            minus_dm.append(0)
                                        elif low_diff > high_diff and low_diff > 0:
                                            plus_dm.append(0)
                                            minus_dm.append(low_diff)
                                        else:
                                            plus_dm.append(0)
                                            minus_dm.append(0)
                                    
                                    tr = []
                                    for k in range(1, len(window)):
                                        h, l, pc = highs[k], lows[k], closes[k-1]
                                        tr.append(max(h-l, abs(h-pc), abs(l-pc)))
                                    
                                    atr = sum(tr) / 14 if tr else 1
                                    plus_di = (sum(plus_dm) / 14 / atr * 100) if atr > 0 else 0
                                    minus_di = (sum(minus_dm) / 14 / atr * 100) if atr > 0 else 0
                                    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
                                    
                                    if dx < 20:
                                        print(f"[BACKTEST] HTF ADX {dx:.0f} < 20 - SKIP (no trend)")
                                        direction_str = None
                            break
                except Exception as e:
                    pass
            
            # HTF Resistance Filter - reduce TP if price near HTF extremes
            if htf_res_candles and direction_str and tp_pct > 0:
                try:
                    current_ts = current_candle.get("timestamp", "")
                    for j, tc in enumerate(htf_res_candles):
                        if tc.get("timestamp", "") >= current_ts:
                            if j > 0:
                                window = htf_res_candles[max(0, j-20):j]
                                htf_high = max(c.get("high", 0) for c in window)
                                htf_low = min(c.get("low", 0) for c in window)
                                htf_range = htf_high - htf_low
                                
                                if htf_range > 0 and current_price > 0:
                                    dist_to_high = (htf_high - current_price) / htf_range
                                    dist_to_low = (current_price - htf_low) / htf_range
                                    
                                    if direction_str == "buy" and dist_to_high < 0.1:
                                        tp_pct = tp_pct * 0.7
                                        print(f"[BACKTEST] Near HTF high - TP to {tp_pct*100:.1f}%")
                                    elif direction_str == "sell" and dist_to_low < 0.1:
                                        tp_pct = tp_pct * 0.7
                                        print(f"[BACKTEST] Near HTF low - TP to {tp_pct*100:.1f}%")
                            break
                except Exception as e:
                    pass
            
            # HTF VWAP Filter - only trade when price is moving toward VWAP
            if htf_vwap_candles and direction_str:
                try:
                    current_ts = current_candle.get("timestamp", "")
                    for j, tc in enumerate(htf_vwap_candles):
                        if tc.get("timestamp", "") >= current_ts:
                            if j > 14:
                                # Calculate VWAP for last 20 candles
                                window = htf_vwap_candles[j-20:j]
                                cum_vol = 0
                                cum_pv = 0
                                for c in window:
                                    h = c.get("high", 0)
                                    l = c.get("low", 0)
                                    c_ = c.get("close", 0)
                                    v = c.get("volume", 0)
                                    if h > 0 and l > 0 and c_ > 0 and v > 0:
                                        typical_price = (h + l + c_) / 3
                                        cum_pv += typical_price * v
                                        cum_vol += v
                                
                                vwap = cum_pv / cum_vol if cum_vol > 0 else 0
                                
                                if vwap > 0 and current_price > 0:
                                    # Check if price is on the "right side" of VWAP
                                    # Buy only if price > VWAP (bullish) or just crossed above
                                    # Sell only if price < VWAP (bearish) or just crossed below
                                    
                                    # Get previous candle
                                    prev_candle = htf_vwap_candles[j-1] if j > 0 else None
                                    prev_vwap = None
                                    if prev_candle and j > 15:
                                        prev_window = htf_vwap_candles[j-21:j-1]
                                        prev_cum_vol = 0
                                        prev_cum_pv = 0
                                        for c in prev_window:
                                            h = c.get("high", 0)
                                            l = c.get("low", 0)
                                            c_ = c.get("close", 0)
                                            v = c.get("volume", 0)
                                            if h > 0 and l > 0 and c_ > 0 and v > 0:
                                                typical_price = (h + l + c_) / 3
                                                prev_cum_pv += typical_price * v
                                                prev_cum_vol += v
                                        prev_vwap = prev_cum_pv / prev_cum_vol if prev_cum_vol > 0 else 0
                                    
                                    # VWAP direction
                                    vwap_up = current_price > vwap
                                    prev_vwap_up = prev_vwap is not None and prev_vwap > 0 and prev_candle.get("close", 0) > prev_vwap if prev_vwap else False
                                    
                                    # Trade with VWAP trend
                                    if direction_str == "buy":
                                        # For buy: price should be above VWAP or crossing above
                                        if current_price < vwap and not (prev_vwap and prev_candle.get("close", 0) < prev_vwap):
                                            print(f"[BACKTEST] HTF VWAP: price below VWAP ({current_price} < {vwap:.0f}) - SKIP")
                                            direction_str = None
                                    elif direction_str == "sell":
                                        # For sell: price should be below VWAP or crossing below
                                        if current_price > vwap and not (prev_vwap and prev_candle.get("close", 0) > prev_vwap):
                                            print(f"[BACKTEST] HTF VWAP: price above VWAP ({current_price} > {vwap:.0f}) - SKIP")
                                            direction_str = None
                            break
                except Exception as e:
                    pass
            
            # Simple HTF Trend Filter - SOFT filter (adjust min_score, not block)
            # Long: HTF RSI > 50, Short: HTF RSI < 50
            # This uses CLOSED HTF candle to avoid look-ahead bias
            if htf_trend_candles and direction_str:
                try:
                    # Find the LAST CLOSED HTF candle (not current one - avoid look-ahead)
                    current_ts = current_candle.get("timestamp", "")
                    htf_index = None
                    for j, tc in enumerate(htf_trend_candles):
                        if tc.get("timestamp", "") >= current_ts:
                            htf_index = max(0, j - 1)  # Use PREVIOUS closed candle
                            break
                    
                    if htf_index is not None and htf_index > 14:
                        window = htf_trend_candles[max(0, htf_index-14):htf_index]
                        closes = [c.get("close", 0) for c in window]
                        if closes and all(c > 0 for c in closes):
                            gains = []
                            losses = []
                            for k in range(1, len(closes)):
                                diff = closes[k] - closes[k-1]
                                if diff > 0:
                                    gains.append(diff)
                                else:
                                    losses.append(abs(diff))
                            avg_gain = sum(gains) / 14 if gains else 0
                            avg_loss = sum(losses) / 14 if losses else 0
                            rs = avg_gain / avg_loss if avg_loss > 0 else 100
                            htf_rsi = 100 - (100 / (1 + rs))
                            
                            # Soft filter: if trading against HTF trend, require HIGHER score
                            if direction_str == "buy" and htf_rsi < 45:
                                # HTF bearish, but we want to buy - require stronger signal
                                min_score_adjusted = min_score * 2  # Double the threshold
                                if abs(score) < min_score_adjusted:
                                    print(f"[BACKTEST] HTF Trend: RSI={htf_rsi:.0f} < 45, need stronger signal - SKIP")
                                    direction_str = None
                            elif direction_str == "sell" and htf_rsi > 55:
                                # HTF bullish, but we want to sell - require stronger signal
                                min_score_adjusted = min_score * 2
                                if abs(score) < min_score_adjusted:
                                    print(f"[BACKTEST] HTF Trend: RSI={htf_rsi:.0f} > 55, need stronger signal - SKIP")
                                    direction_str = None
                except Exception as e:
                    pass
            
            # Divergence Filter - check for price/indicator divergence
            if divergence_filter and direction_str:
                try:
                    div_indicator = divergence_filter.upper().strip()
                    if div_indicator in ["RSI", "MACD", "STOCH"]:
                        # Get indicator values
                        if div_indicator == "RSI":
                            rsi_val = indicators.get("RSI", {}).get("value", 50)
                            # Need previous RSI from earlier in window
                            if i > 60:
                                prev_indicators = TechnicalIndicators.calculate_all(candle_window[:-1], period=14)
                                prev_rsi = prev_indicators.get("RSI", {}).get("value", 50)
                                
                                # Check divergence
                                prev_price = candle_window[-2].get("close", 0) if len(candle_window) > 1 else current_price
                                
                                # Bearish divergence: price higher, RSI lower
                                if direction_str == "buy" and current_price > prev_price and rsi_val < prev_rsi:
                                    print(f"[BACKTEST] Divergence: bearish - SKIP")
                                    direction_str = None
                                # Bullish divergence: price lower, RSI higher
                                elif direction_str == "sell" and current_price < prev_price and rsi_val > prev_rsi:
                                    print(f"[BACKTEST] Divergence: bullish - SKIP")
                                    direction_str = None
                except Exception as e:
                    pass
            
            # Order Block Filter - only trade from order blocks
            if order_block_filter and direction_str:
                try:
                    # Look for recent order block (last 5 candles)
                    for ob_idx in range(max(1, i-5), i):
                        if ob_idx < len(candles):
                            ob_candle = candles[ob_idx]
                            ob_close = ob_candle.get("close", 0)
                            ob_open = ob_candle.get("open", 0)
                            ob_is_green = ob_close > ob_open
                            
                            # Check if price is returning to OB zone
                            if direction_str == "buy" and ob_is_green:
                                # Green OB = buy order block, look for price return to it
                                ob_high = ob_candle.get("high", 0)
                                if current_price >= ob_high * 0.99 and current_price <= ob_high * 1.02:
                                    # Price at or near OB high - good entry
                                    pass
                            elif direction_str == "sell" and not ob_is_green:
                                ob_low = ob_candle.get("low", 0)
                                if current_price <= ob_low * 1.01 and current_price >= ob_low * 0.98:
                                    # Price at or near OB low - good entry
                                    pass
                            else:
                                # Price not at OB - skip
                                if direction_str == "buy":
                                    print(f"[BACKTEST] Order Block: price not at buy OB - SKIP")
                                    direction_str = None
                                else:
                                    print(f"[BACKTEST] Order Block: price not at sell OB - SKIP")
                                    direction_str = None
                            break
                except Exception as e:
                    pass
            
            # Open trade with leverage
            if direction_str:
                price = current_price
                risk_amount = balance * risk_pct
                # With leverage: size = (balance * risk_pct * leverage) / price
                size = (risk_amount * leverage) / price

                open_trade = {
                    "id": str(uuid.uuid4())[:8],
                    "symbol": symbol_key,
                    "direction": direction_str,
                    "entry_price": price,
                    "size": size,
                    "leverage": leverage,
                    "risk_pct": risk_pct,
                    "tp_pct": tp_pct,
                    "sl_pct": sl_pct,
                    "trailing_sl_pct": trailing_sl_pct,
                    "trailing_sl_activated": False,
                    "opened_at": current_candle.get("timestamp", ""),
                    "opened_at_candle": i,  # Track which candle we opened at
                    "balance_at_entry": balance,
                    "tp": tp,
                    "sl": sl,
                }

        # Check close conditions
        if open_trade:
            price = current_candle.get("close", 0)
            entry = open_trade["entry_price"]
            direction = open_trade["direction"]
            tp_pct = open_trade.get("tp_pct", 0.02)
            sl_pct = open_trade.get("sl_pct", 0.01)
            trailing_sl_pct = open_trade.get("trailing_sl_pct", 0)
            trailing_sl_activated = open_trade.get("trailing_sl_activated", False)
            
            # Dynamic TP adjustment based on HTF (only adjust, never increase TP)
            original_tp_pct = tp_pct
            if htf_rsi_candles:
                try:
                    current_ts = current_candle.get("timestamp", "")
                    for j, tc in enumerate(htf_rsi_candles):
                        if tc.get("timestamp", "") >= current_ts:
                            if j > 14:
                                window = htf_rsi_candles[j-14:j]
                                closes = [c.get("close", 0) for c in window]
                                if closes and all(c > 0 for c in closes):
                                    gains = []
                                    losses = []
                                    for k in range(1, len(closes)):
                                        diff = closes[k] - closes[k-1]
                                        if diff > 0:
                                            gains.append(diff)
                                        else:
                                            losses.append(abs(diff))
                                    avg_gain = sum(gains) / 14 if gains else 0
                                    avg_loss = sum(losses) / 14 if losses else 0
                                    rs = avg_gain / avg_loss if avg_loss > 0 else 100
                                    rsi = 100 - (100 / (1 + rs))
                                    
                                    # Adjust TP based on HTF RSI (only reduce, never increase)
                                    if direction == "buy" and rsi > 65:
                                        tp_pct = min(tp_pct, 0.03)  # Reduce TP if overbought
                                    elif direction == "buy" and rsi < 40:
                                        tp_pct = max(tp_pct, 0.06)  # Increase TP if oversold (more room)
                                    elif direction == "sell" and rsi < 35:
                                        tp_pct = min(tp_pct, 0.03)
                                    elif direction == "sell" and rsi > 60:
                                        tp_pct = max(tp_pct, 0.06)
                except Exception as e:
                    pass
            
            # Update trade with adjusted TP
            open_trade["tp_pct"] = tp_pct

            # Use percentage-based TP/SL
            tp_price = entry * (1 + tp_pct) if direction == "buy" else entry * (1 - tp_pct)
            sl_price = entry * (1 - sl_pct) if direction == "buy" else entry * (1 + sl_pct)

            closed = False
            pnl = 0

            # Calculate current profit/loss %
            if direction == "buy":
                profit_pct = (price - entry) / entry
            else:
                profit_pct = (entry - price) / entry

            # Trailing SL: if profit > trailing_sl_pct, move SL to breakeven
            if trailing_sl_pct > 0 and not trailing_sl_activated and profit_pct >= trailing_sl_pct:
                # Activate trailing SL - move SL to breakeven
                trailing_sl_activated = True
                if direction == "buy":
                    sl_price = entry  # Move SL to entry price
                else:
                    sl_price = entry  # Move SL to entry price
                open_trade["trailing_sl_activated"] = True
                open_trade["trailing_sl_price"] = sl_price
            elif trailing_sl_activated:
                # Update trailing SL - move it up as price moves
                if direction == "buy":
                    new_sl = entry + (price - entry) * 0.5  # Keep 50% of profits
                    if new_sl > sl_price:
                        sl_price = new_sl
                        open_trade["trailing_sl_price"] = sl_price
                else:
                    new_sl = entry - (entry - price) * 0.5
                    if new_sl < sl_price:
                        sl_price = new_sl
                        open_trade["trailing_sl_price"] = sl_price

            if direction == "buy":
                if price >= tp_price:  # TP
                    pnl = (price - entry) * open_trade["size"]
                    closed = True
                elif price <= sl_price:  # SL (or trailing SL)
                    pnl = (price - entry) * open_trade["size"]
                    closed = True
            else:  # sell
                if price <= tp_price:  # TP
                    pnl = (entry - price) * open_trade["size"]
                    closed = True
                elif price >= sl_price:  # SL (or trailing SL)
                    pnl = (entry - price) * open_trade["size"]
                    closed = True

            if closed:
                balance += pnl
                peak_balance = max(peak_balance, balance)

                trade_result = {
                    **open_trade,
                    "exit_price": price,
                    "closed_at": current_candle.get("timestamp", ""),
                    "pnl_usd": pnl,
                    "result": "win" if pnl > 0 else "loss",
                }
                trades.append(trade_result)
                open_trade = None
            else:
                # Close position if open for too long (max 4 hours / 240 minutes of candles)
                candles_open = i - open_trade.get("opened_at_candle", i)
                if candles_open > 240:  # 240 candles = 4 hours for 1min resolution
                    # Close at market price
                    pnl = 0
                    if direction == "buy":
                        pnl = (price - entry) * open_trade["size"]
                    else:
                        pnl = (entry - price) * open_trade["size"]
                    balance += pnl
                    trade_result = {
                        **open_trade,
                        "exit_price": price,
                        "closed_at": current_candle.get("timestamp", ""),
                        "pnl_usd": pnl,
                        "result": "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven"),
                    }
                    trades.append(trade_result)
                    open_trade = None

    # Close any remaining open positions at last candle price
    if open_trade:
        last_price = candles[-1].get("close", 0)
        entry = open_trade["entry_price"]
        direction = open_trade["direction"]
        if direction == "buy":
            pnl = (last_price - entry) * open_trade["size"]
        else:
            pnl = (entry - last_price) * open_trade["size"]
        balance += pnl
        trade_result = {
            **open_trade,
            "exit_price": last_price,
            "closed_at": candles[-1].get("timestamp", ""),
            "pnl_usd": pnl,
            "result": "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven"),
        }
        trades.append(trade_result)

    # Calculate metrics
    winning_trades = [t for t in trades if t["pnl_usd"] > 0]
    losing_trades = [t for t in trades if t["pnl_usd"] <= 0]
    win_rate = len(winning_trades) / len(trades) if trades else 0

    # Max drawdown
    max_dd = 0
    running_balance = initial_balance
    for t in trades:
        running_balance += t["pnl_usd"]
        dd = (peak_balance - running_balance) / peak_balance
        max_dd = max(max_dd, dd)

    duration = time.time() - start_time

    return {
        "symbol": symbol_key,
        "resolution": resolution,
        "config": strategy.to_config(enabled_indicators),
        "period": {
            "from": candles[0].get("timestamp", "")[:10],
            "to": candles[-1].get("timestamp", "")[:10],
        },
        "trades_count": len(trades),
        "trades": trades[:200],  # Return up to 200 trades
        "metrics": {
            "initial_balance": initial_balance,
            "final_balance": balance,
            "total_pnl": balance - initial_balance,
            "win_rate": round(win_rate * 100, 1),
            "max_drawdown_pct": round(max_dd * 100, 1),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "duration_seconds": round(duration, 2),
        },
    }


# EXTRACTED TO api/routes/backtest.py - using router below
# @app.get("/api/backtest/optimize")
# async def start_optimize(
#     symbol: str = Query(..., description="Symbol to backtest"),
#     resolution: str = Query("60", description="Resolution: 1, 5, 15, 30, 60, D"),
#     days: int = Query(7, description="Number of days to backtest (keep small)"),
#     min_score: float = Query(0.05, description="Minimum score threshold"),
#     initial_balance: float = Query(3000.0, description="Initial balance"),
#     background_tasks: BackgroundTasks = None,
# ):
#     """
#     Start optimization in background. Returns job_id immediately.
#     Use /api/backtest/optimize/{job_id} to get results.
#     """
#     import uuid
#     from database import get_db
#     
#     job_id = str(uuid.uuid4())[:8]
#     
#     # Store initial status in DB
#     db = get_db()
#     db.optimize_jobs.insert_one({
#         "_id": job_id,
#         "status": "running",
#         "symbol": symbol,
#         "started_at": datetime.utcnow().isoformat(),
#     })
#     
#     # Run in background
#     background_tasks.add_task(
#         run_optimization, job_id, symbol, resolution, days, min_score, initial_balance
#     )
#     
#     return {
#         "job_id": job_id,
#         "status": "started",
#         "symbol": symbol,
#         "message": "Optimization started in background. Poll /api/backtest/optimize/{job_id} for results."
#     }


# DEAD CODE - was used by start_optimize above (extracted to backtest.py)
# def run_optimization(job_id: str, symbol: str, resolution: str, days: int, min_score: float, initial_balance: float):
    """Run optimization in background and save results to DB"""
    import subprocess
    import json
    from database import get_db
    from strategies import STRATEGIES
    
    print(f"[OPTIMIZE] Starting job {job_id} for {symbol}")
    db = get_db()
    
    try:
        # Get available indicators - limit to first 3
        ALL_INDICATORS = ["RSI", "MACD", "BB", "SMA", "ADX", "STOCH", "MOMENTUM"]
        
        # Get all strategies
        all_strategies = list(STRATEGIES.keys())
        
        # Generate combinations - more indicators for better results
        combinations = []
        for strat in all_strategies:
            # Single indicators
            for ind in ALL_INDICATORS:
                combinations.append({"strategy": strat, "indicators": [ind]})
            # Pairs of indicators
            for i, ind1 in enumerate(ALL_INDICATORS):
                for ind2 in ALL_INDICATORS[i+1:]:
                    if len(combinations) < 30:  # Limit to 30
                        combinations.append({"strategy": strat, "indicators": [ind1, ind2]})
        
        # Save total combinations count
        db.optimize_jobs.update_one(
            {"_id": job_id},
            {"$set": {"total_combinations": len(combinations)}}
        )
        
        results = []
        for combo in combinations:
            # Check if cancelled
            job = db.optimize_jobs.find_one({"_id": job_id})
            if job and job.get("status") == "cancelled":
                break
            
            strat = combo["strategy"]
            inds = combo["indicators"]
            ind_str = ",".join(inds)
            
            try:
                # Call backtest endpoint using subprocess
                url = f"http://localhost:9000/api/backtest?symbol={symbol}&resolution={resolution}&days={days}&min_score={min_score}&initial_balance={initial_balance}&strategy={strat}&indicators={ind_str}"
                result = subprocess.run(["curl", "-s", url], capture_output=True, timeout=60)
                if result.returncode == 0:
                    try:
                        data = json.loads(result.stdout)
                        if "error" not in data and data.get("trades_count", 0) > 0:
                            result = {
                                "strategy": strat,
                                "indicators": inds,
                                "trades_count": data["trades_count"],
                                "total_pnl": data["metrics"]["total_pnl"],
                                "win_rate": data["metrics"]["win_rate"],
                                "max_drawdown_pct": data["metrics"]["max_drawdown_pct"],
                                "score": data["metrics"]["total_pnl"] - (data["metrics"]["max_drawdown_pct"] * 10),
                            }
                            results.append(result)
                        
                        # Save partial results to DB for live updates
                        sorted_partial = sorted(results, key=lambda x: x["score"], reverse=True)
                        db.optimize_jobs.update_one(
                            {"_id": job_id},
                            {"$set": {
                                "results": sorted_partial[:10],
                                "best": sorted_partial[0] if sorted_partial else None,
                            }}
                        )
                    except Exception:
                        pass
            except Exception as e:
                print(f"[OPTIMIZE] Error: {e}")
                pass
        
        # Sort results
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Save to DB
        db.optimize_jobs.update_one(
            {"_id": job_id},
            {"$set": {
                "status": "completed",
                "results": results[:10],
                "best": results[0] if results else None,
                "completed_at": datetime.utcnow().isoformat(),
            }}
        )
    except Exception as e:
        db.optimize_jobs.update_one(
            {"_id": job_id},
            {"$set": {"status": "failed", "error": str(e)}}
        )


# EXTRACTED TO api/routes/backtest.py - using router below
# @app.get("/api/backtest/optimize/{job_id}")
# async def get_optimize_results(job_id: str):
#     """Get optimization results by job_id"""
#     from database import get_db
#     db = get_db()
#     job = db.optimize_jobs.find_one({"_id": job_id})
#     
#     if not job:
#         return {"error": "Job not found"}
#     
#     return {
#         "job_id": job_id,
#         "status": job.get("status"),
#         "symbol": job.get("symbol"),
#         "best": job.get("best"),
#         "results": job.get("results", []),
#         "total": job.get("total_combinations", 0),
#     }


# EXTRACTED TO api/routes/backtest.py - using router below
# @app.post("/api/backtest/optimize/{job_id}/cancel")
# async def cancel_optimize(job_id: str):
#     """Cancel a running optimization job"""
#     from database import get_db
#     db = get_db()
#     db.optimize_jobs.update_one(
#         {"_id": job_id},
#         {"$set": {"status": "cancelled"}}
#     )
#     return {"status": "cancelled"}

    # Get available strategies
    from strategies import STRATEGIES

    all_strategies = [s.strip() for s in strategies.split(",")] if strategies else list(STRATEGIES.keys())

    # Get available indicators - limit to first 3 for speed
    ALL_INDICATORS = ["RSI", "MACD", "BB", "SMA", "ADX", "STOCH", "MOMENTUM"]
    all_indicators = [ind.strip().upper() for ind in indicators.split(",")] if indicators else ALL_INDICATORS[:3]  # Limit to 3 for speed

    # Generate combinations - limit count
    combinations = []
    for strat in all_strategies:
        # Single indicators only (for speed)
        for ind in all_indicators:
            combinations.append({"strategy": strat, "indicators": [ind]})

    print(f"[OPTIMIZE] Testing {len(combinations)} combinations (parallel)...")

    # Run backtests in parallel
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def run_single_combo(combo):
        strat = combo["strategy"]
        inds = combo["indicators"]
        ind_str = ",".join(inds)
        # Build URL inside function
        combo_url = f"http://127.0.0.1:8002/api/backtest?symbol={symbol}&resolution={resolution}&days={days}&min_score={min_score}&initial_balance={initial_balance}&strategy={strat}&indicators={ind_str}"
        try:
            resp = requests.get(combo_url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if "error" not in data and data.get("trades_count", 0) > 0:
                    return {
                        "strategy": strat,
                        "indicators": inds,
                        "trades_count": data["trades_count"],
                        "total_pnl": data["metrics"]["total_pnl"],
                        "win_rate": data["metrics"]["win_rate"],
                        "max_drawdown_pct": data["metrics"]["max_drawdown_pct"],
                        "score": data["metrics"]["total_pnl"] - (data["metrics"]["max_drawdown_pct"] * 10),
                    }
        except Exception as e:
            pass
        return None

    # Run in parallel
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(run_single_combo, combo): combo for combo in combinations}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    print(f"[OPTIMIZE] Completed {len(results)} tests")

    # Sort by score (PnL - drawdown penalty)
    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "symbol": symbol,
        "period_days": days,
        "total_combinations": len(combinations),
        "tested": len(results),
        "best": results[0] if results else None,
        "results": results[:20],  # Top 20
    }


# @app.get("/api/dashboard")
# @async_timed("dashboard")
# async def get_dashboard(resolution: str = Query("60"), count: int = Query(50)):
#     symbols = list(INSTRUMENTS.keys())
#     account_task = async_load_account()
#     signals_task = generate_signals()
#     open_task = async_load_open_positions()
#     closed_task = async_load_closed_positions(20)
#     chart_tasks = [get_chart_data(s, resolution=resolution, count=count) for s in symbols]
#     news_tasks = [get_news(s) for s in symbols]
#     account, signals, open_pos, closed_pos = await asyncio.gather(account_task, signals_task, open_task, closed_task)
#     charts_results = await asyncio.gather(*chart_tasks, return_exceptions=True)
#     news_results = await asyncio.gather(*news_tasks, return_exceptions=True)
#     charts = {}
#     news_dict = {}
#     for i, sym in enumerate(symbols):
#         res_chart = charts_results[i]
#         if isinstance(res_chart, dict) and "data" in res_chart:
#             charts[sym] = res_chart
#         res_news = news_results[i]
#         if isinstance(res_news, dict) and "news" in res_news:
#             news_dict[sym] = res_news["news"]
#     return {
#         "account": account,
#         "signals": signals,
#         "open_positions": open_pos[:20],
#         "closed_positions": closed_pos[:20],
#         "charts": charts,
#         "news": news_dict,
#     }


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


# =====================
# STRATEGY MODULE - Moved to services/strategy_manager.py
# =====================
# Import from service instead of defining locally
# from services.strategy_manager import get_strategy_manager, analyze_with_new_strategy
# (Imported at top of file)

# Legacy code commented out - now using services.strategy_manager:
# # Global strategy manager - loaded once
# _strategy_manager = None

# def get_strategy_manager(force_reload: bool = False):
#     """Get or create the JSON-based strategy manager."""
#     ... (moved to services/strategy_manager.py)

# def analyze_with_new_strategy(...):
#     ... (moved to services/strategy_manager.py)

