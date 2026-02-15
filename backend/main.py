"""
CFD Trading Bot - FastAPI Backend
Real-time signal generation using Finnhub data and technical indicators
Simulated trading engine with PLN currency
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import uvicorn
import asyncio
from typing import Dict, List, Optional
import os
import json
import uuid
from dotenv import load_dotenv

# Load env vars BEFORE importing modules that need them
load_dotenv()

from models import Signal, SignalDirection, Component, ComponentType, SignalResponse
from alpha_vantage import get_client as get_alpha_vantage_client
from alpha_vantage_news import get_client as get_news_client
from indicators import TechnicalIndicators
from strategies import get_strategy, list_strategies, mms_on_trade_result
from imessage_alerts import AlertConfig, iMessageAlertDispatcher, get_dispatcher
from openclaw_integration import set_openclaw_message_function, format_imessage_for_cfd_alert
import database as db
from database import (
    async_load_account, async_save_account,
    async_load_open_positions, async_load_closed_positions, async_save_trade,
    async_load_candle_history, async_store_candles, async_load_candles, async_save_candles,
    async_load_signal_cache_db, async_save_signal_cache_db,
    async_save_event_log, async_load_event_log, async_count_closed_positions,
    async_count_candles, async_get_candle_date_range
)
from broker_factory import create_broker, create_data_provider

# =============================================================================
# TIMING PROFILER - Performance monitoring
# =============================================================================
import time
import functools
from typing import Callable, Any

_timing_stats: dict[str, dict] = {}

def async_timed(label: str | None = None):
    """Decorator to measure async function execution time."""
    def decorator(func: Callable) -> Callable:
        func_name = label or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                if func_name not in _timing_stats:
                    _timing_stats[func_name] = {"calls": 0, "total": 0.0, "min": float('inf'), "max": 0.0}
                _timing_stats[func_name]["calls"] += 1
                _timing_stats[func_name]["total"] += elapsed
                _timing_stats[func_name]["min"] = min(_timing_stats[func_name]["min"], elapsed)
                _timing_stats[func_name]["max"] = max(_timing_stats[func_name]["max"], elapsed)
                # Log to console immediately (flush for visibility)
                print(f"[TIMING] {func_name}: {elapsed:.3f}s", flush=True)
                # Late binding for log_event (defined later in file)
                try:
                    log_event(f"[TIMING] {func_name}: {elapsed:.3f}s", "info")
                except NameError:
                    pass
        
        return wrapper
    return decorator

def sync_timed(label: str | None = None):
    """Decorator to measure sync function execution time."""
    def decorator(func: Callable) -> Callable:
        func_name = label or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                if func_name not in _timing_stats:
                    _timing_stats[func_name] = {"calls": 0, "total": 0.0, "min": float('inf'), "max": 0.0}
                _timing_stats[func_name]["calls"] += 1
                _timing_stats[func_name]["total"] += elapsed
                _timing_stats[func_name]["min"] = min(_timing_stats[func_name]["min"], elapsed)
                _timing_stats[func_name]["max"] = max(_timing_stats[func_name]["max"], elapsed)
                print(f"[TIMING] {func_name}: {elapsed:.3f}s", flush=True)
                try:
                    log_event(f"[TIMING] {func_name}: {elapsed:.3f}s", "info")
                except NameError:
                    pass
        
        return wrapper
    return decorator

# =============================================================================
# LIFESPAN HANDLER - Startup/Shutdown events (replaces deprecated @app.on_event)
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    global _trading_task, alpha_client

    # STARTUP
    log_event("[CFD TRADING BOT v0.2.0 - PLN SIMULATION]", "event")
    log_event("Instruments: XAU (Gold), XAG (Silver), US100 (Nasdaq), BTC (Bitcoin)", "info")

    # Database status
    if db.is_connected():
        log_event("MongoDB connected – trades & account persisted", "success")
        log_event(f"Restored {len(open_positions)} open positions, {len(closed_positions)} closed trades", "info")
        db.ensure_candle_indexes()
        log_event("Candle history indexes ensured", "info")
    else:
        log_event("MongoDB not configured – using in-memory storage (set MONGO_URI)", "warning")

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
    log_event(f"Account loaded: {account['balance_pln']:.2f} PLN ({account['balance_usd']:.2f} USD)", "success")

    # Start autonomous trading loop
    _trading_task = asyncio.create_task(auto_trade_loop())
    log_event("[AUTO-TRADE] Background task launched (5 min interval)", "success")

    yield  # App runs here

    # SHUTDOWN
    if _trading_task:
        _trading_task.cancel()
        try:
            await _trading_task
        except asyncio.CancelledError:
            pass
    await async_save_signal_cache_db(signal_history_cache)
    await async_save_account(account)
    await async_save_event_log(event_log)
    try:
        news_client = get_news_client()
        if hasattr(news_client, 'close'):
            await news_client.close()
    except Exception:
        pass
    log_event("[CFD TRADING BOT] Shutdown complete – state saved", "event")

# =============================================================================

app = FastAPI(
    title="CFD Trading Bot API",
    description="Real-time trading signals for CFD instruments with simulated trading",
    version="0.2.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PLN/USD exchange rate (approximate)
PLN_USD_RATE = 4.05

# Global state
signals_cache = {}
alpha_client = None
event_log = db.load_event_log()  # Restore log from DB on startup

# Broker abstraction – switch via BROKER_TYPE env var ("sim" or "ibkr")
data_provider = create_data_provider()
broker = create_broker(data_provider)

# Convenience references (broker owns this state)
account = broker.get_account()
open_positions = broker.get_open_positions() if hasattr(broker, 'open_positions') else []
closed_positions = broker.get_closed_positions() if hasattr(broker, 'closed_positions') else []

# For SimulatedBroker, keep direct references to the same lists
if hasattr(broker, 'open_positions'):
    open_positions = broker.open_positions
if hasattr(broker, 'closed_positions'):
    closed_positions = broker.closed_positions
if hasattr(broker, 'account'):
    account = broker.account

# Signal history cache for trend analysis
signal_history_cache = {}

# Strategy selection per symbol (default: adaptive_regime)
_strategy_selection: Dict[str, str] = {}

def get_symbol_strategy(symbol: str) -> str:
    return _strategy_selection.get(symbol, "adaptive_regime")

def set_symbol_strategy(symbol: str, strategy_id: str):
    _strategy_selection[symbol] = strategy_id

def load_signal_cache():
    """Load signal history cache from DB, fallback to JSON file"""
    global signal_history_cache
    # Try MongoDB first
    cached = db.load_signal_cache_db()
    if cached:
        signal_history_cache = cached
        log_event(f"Loaded signal cache from DB ({len(signal_history_cache)} symbols)")
        return
    # Fallback to JSON file
    try:
        cache_file = "signal_cache.json"
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                signal_history_cache = json.load(f)
            log_event(f"Loaded signal cache from file ({len(signal_history_cache)} symbols)")
    except Exception as e:
        log_event(f"Failed to load signal cache: {e}", "warning")
        signal_history_cache = {}

def save_signal_cache():
    """Save signal history cache to DB + JSON file"""
    db.save_signal_cache_db(signal_history_cache)
    try:
        cache_file = "signal_cache.json"
        with open(cache_file, 'w') as f:
            json.dump(signal_history_cache, f)
    except Exception:
        pass  # File write is best-effort fallback

# Instruments to monitor — with per-instrument signal tuning
# leverage: position multiplier (x20 = 5% margin requirement)
# min_score: minimum |score| to enter (higher = fewer but better trades)
# asset_class: "commodity" (mean-reverting) or "equity"/"crypto" (trending)
# trailing_stop: enable trailing SL that locks in profits once in the green
INSTRUMENTS = {
    "XAU": {"name": "Gold", "multiplier": 1, "pip_size": 0.01, "lot_size": 1,
            "leverage": 20, "min_score": 0.30, "asset_class": "commodity",
            "trailing_stop": True},
    "XAG": {"name": "Silver", "multiplier": 1, "pip_size": 0.001, "lot_size": 100,
            "leverage": 20, "min_score": 0.28, "asset_class": "commodity",
            "trailing_stop": True},
    "US100": {"name": "Nasdaq-100", "multiplier": 1, "pip_size": 0.01, "lot_size": 1,
              "leverage": 20, "min_score": 0.20, "asset_class": "equity",
              "trailing_stop": True},
    "BTC": {"name": "Bitcoin", "multiplier": 1, "pip_size": 1.0, "lot_size": 0.01,
            "leverage": 5, "min_score": 0.20, "asset_class": "crypto",
            "trailing_stop": True},
}

_log_counter = 0

def log_event(message: str, log_type: str = "info"):
    """Log events for the console. Persists to DB every 10 entries."""
    global _log_counter
    event_log.append({
        "id": str(len(event_log)),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "message": message,
        "type": log_type
    })
    if len(event_log) > 200:
        event_log.pop(0)
    print(f"[{log_type.upper()}] {message}")
    # Persist periodically (every 10 log entries) to avoid excessive DB writes
    _log_counter += 1
    if _log_counter % 10 == 0:
        # Run DB save in background - don't block
        asyncio.create_task(async_save_event_log(event_log))

def calculate_signal_score(indicators: dict, symbol: str = "") -> tuple[float, List[Component]]:
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
        components.append(Component(
            type=ComponentType.TECHNICAL,
            name="ADX (Trend)",
            value=max(-1, min(1, (adx_value - 25) / 25)) if trend_dir == "UP" else max(-1, min(1, -(adx_value - 25) / 25)),
            description=f"ADX {adx_value:.0f} ({regime}, {trend_dir}) +DI:{adx_data['plus_di']:.0f} -DI:{adx_data['minus_di']:.0f}",
            confidence=0.8 if adx_value > 30 else 0.5,
            indicators=adx_data
        ))

    # --- RSI Component (FIXED: oversold=BUY, overbought=SELL) ---
    if indicators.get("rsi_14") is not None:
        rsi = indicators["rsi_14"]
        # Correct interpretation: low RSI = oversold = buy opportunity
        if rsi < 30:
            rsi_score = (30 - rsi) / 30        # Oversold → positive (BUY)
        elif rsi > 70:
            rsi_score = -((rsi - 70) / 30)     # Overbought → negative (SELL)
        elif rsi < 45:
            rsi_score = (45 - rsi) / 45 * 0.3  # Mild bullish bias
        elif rsi > 55:
            rsi_score = -(rsi - 55) / 45 * 0.3 # Mild bearish bias
        else:
            rsi_score = 0                       # Dead neutral zone

        rsi_score = max(-1, min(1, rsi_score))
        zone = "OVERSOLD" if rsi < 30 else "OVERBOUGHT" if rsi > 70 else "NEUTRAL"

        # RSI weight depends on regime: higher in ranging, lower in trending
        rsi_weight = 0.15 if is_trending else 0.25

        components.append(Component(
            type=ComponentType.TECHNICAL,
            name="RSI (14)",
            value=rsi_score,
            description=f"RSI {rsi:.1f} ({zone})",
            confidence=0.85 if abs(rsi - 50) > 20 else 0.5,
            indicators={"value": rsi, "zone": zone}
        ))
        scores.append(rsi_score)
        weights.append(rsi_weight)

    # --- StochRSI Component (entry timing) ---
    stoch = indicators.get("stoch_rsi")
    if stoch:
        k, d = stoch["k"], stoch["d"]
        if k < 20:
            stoch_score = 0.6 + (20 - k) / 50   # Oversold → BUY
        elif k > 80:
            stoch_score = -(0.6 + (k - 80) / 50) # Overbought → SELL
        else:
            stoch_score = 0

        # Crossover confirmation: %K crossing above %D = bullish
        if k > d and k < 30:
            stoch_score = max(stoch_score, 0.5)
        elif k < d and k > 70:
            stoch_score = min(stoch_score, -0.5)

        stoch_score = max(-1, min(1, stoch_score))
        if abs(stoch_score) > 0.1:
            components.append(Component(
                type=ComponentType.TECHNICAL,
                name="StochRSI",
                value=stoch_score,
                description=f"StochRSI K:{k:.0f} D:{d:.0f}",
                confidence=0.7 if abs(k - 50) > 30 else 0.4,
                indicators=stoch
            ))
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
            # MACD weight: higher in trending markets
            macd_weight = 0.25 if is_trending else 0.15

            components.append(Component(
                type=ComponentType.TECHNICAL,
                name="MACD",
                value=macd_score,
                description=f"MACD {cross} | hist/ATR: {norm_hist:.2f}",
                confidence=0.8 if abs(norm_hist) > 0.5 else 0.5,
                indicators=macd
            ))
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

            components.append(Component(
                type=ComponentType.TECHNICAL,
                name="Bollinger Bands",
                value=max(-1, min(1, bb_score)),
                description=f"BB {zone} (pos: {bb_position:.2f})",
                confidence=0.75 if abs(bb_position) > 0.8 else 0.4,
                indicators={"position": bb_position, "zone": zone}
            ))
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

            components.append(Component(
                type=ComponentType.TECHNICAL,
                name="SMA Cross (20/50)",
                value=sma_score,
                description=f"SMA20/50: {sma_diff_pct:.2f}% ({trend})",
                confidence=0.7,
                indicators={"sma_20": sma_20, "sma_50": sma_50, "trend": trend}
            ))
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
            components.append(Component(
                type=ComponentType.TECHNICAL,
                name="Volume",
                value=vol_bias,
                description=f"Vol {vol_ratio:.1f}x avg | Up/Down: {up_down:.1f}",
                confidence=0.6,
                indicators=vol
            ))
            scores.append(vol_bias)
            weights.append(0.10)

    # --- Momentum (reduced weight, confirmation only) ---
    if indicators.get("momentum_10") is not None:
        momentum = indicators["momentum_10"]
        base_price = indicators.get("sma_20", 1) or 1
        mom_pct = (momentum / base_price) * 100 if base_price else 0
        momentum_score = max(-1, min(1, mom_pct / 2))

        components.append(Component(
            type=ComponentType.TECHNICAL,
            name="Momentum (10)",
            value=momentum_score,
            description=f"Momentum: {mom_pct:.2f}%",
            confidence=0.6,
            indicators={"value": momentum, "pct": mom_pct}
        ))
        scores.append(momentum_score)
        weights.append(0.05)

    # --- Candlestick Patterns ---
    cp = indicators.get("candlestick_patterns")
    if cp and cp.get("patterns") and abs(cp["net_bias"]) > 0.1:
        pattern_names = ", ".join(p["name"] for p in cp["patterns"])
        cp_score = max(-1, min(1, cp["net_bias"]))
        components.append(Component(
            type=ComponentType.TECHNICAL,
            name="Candlestick Patterns",
            value=cp_score,
            description=f"Patterns: {pattern_names} (bias: {cp['net_bias']:.2f})",
            confidence=0.7,
            indicators={"patterns": [p["name"] for p in cp["patterns"]], "net_bias": cp["net_bias"]}
        ))
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
            composite_score *= 0.7   # Dampen when components disagree

    return max(-1, min(1, composite_score)), components


def get_signal_direction(score: float, min_score: float = 0.15) -> SignalDirection:
    """Determine signal direction from score with per-instrument thresholds."""
    strong_threshold = max(0.45, min_score + 0.20)
    if score > strong_threshold:
        return SignalDirection.STRONG_BUY
    elif score > min_score:
        return SignalDirection.BUY
    elif score < -strong_threshold:
        return SignalDirection.STRONG_SELL
    elif score < -min_score:
        return SignalDirection.SELL
    else:
        return SignalDirection.NEUTRAL


# ── Risk Management ──────────────────────────────────────────────────

MAX_DRAWDOWN_PCT = 20.0      # Stop trading if account drops 20% from peak
MAX_OPEN_POSITIONS = 3        # Max concurrent positions
MAX_RISK_PER_TRADE_PCT = 2.0  # Risk max 2% of balance per trade
INITIAL_BALANCE_PLN = 10000.0

def check_circuit_breaker() -> tuple[bool, str]:
    """Check if trading should be halted due to drawdown or position limits."""
    peak_balance = max(INITIAL_BALANCE_PLN, account.get("peak_balance_pln", INITIAL_BALANCE_PLN))
    current = account["balance_pln"]
    drawdown_pct = ((peak_balance - current) / peak_balance) * 100 if peak_balance > 0 else 0

    if drawdown_pct >= MAX_DRAWDOWN_PCT:
        return False, f"CIRCUIT BREAKER: {drawdown_pct:.1f}% drawdown exceeds {MAX_DRAWDOWN_PCT}% limit"

    if len(open_positions) >= MAX_OPEN_POSITIONS:
        return False, f"Max {MAX_OPEN_POSITIONS} positions reached"

    return True, "OK"

def calculate_position_size(symbol: str, entry_price: float, stop_loss: float) -> float:
    """
    Calculate position size based on risk per trade and leverage.
    Risks MAX_RISK_PER_TRADE_PCT of account balance per trade.
    Leverage amplifies both gains and losses — size is adjusted so that
    the max loss on a SL hit still equals the risk amount.
    """
    info = INSTRUMENTS.get(symbol, {})
    leverage = info.get("leverage", 1)

    risk_amount_pln = account["balance_pln"] * (MAX_RISK_PER_TRADE_PCT / 100)
    risk_amount_usd = risk_amount_pln / PLN_USD_RATE

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

    return round(max(min_size, min(size, max_size)), 4)

def update_account_equity():
    """Update account equity based on open positions via broker."""
    broker.update_prices(data_provider)

# Semaphore to limit concurrent API calls
_api_semaphore = asyncio.Semaphore(2)

async def _analyze_single_symbol(symbol: str, info: dict, news_client_instance) -> Signal:
    """Analyze a single symbol - runs in parallel for all symbols."""
    try:
        # Use asyncio.to_thread with timeout for blocking operations
        async with _api_semaphore:
            quote = await asyncio.wait_for(
                asyncio.to_thread(data_provider.get_quote, symbol),
                timeout=5.0
            )
        if not quote:
            return Signal(
                symbol=symbol, direction=SignalDirection.NEUTRAL, score=0.0,
                confidence=0.0, technical_score=0.0, price_action_score=0.0,
                news_score=0.0, components=[], current_price=0.0,
                time_horizon="1h", entry_point=0.0, take_profit=0.0,
                stop_loss=0.0, risk_reward_ratio=0.0,
            )

        current_price = quote["price"]

        async with _api_semaphore:
            candles = await asyncio.wait_for(
                asyncio.to_thread(data_provider.get_candles, symbol, "60", 100),
                timeout=10.0
            )
        if not candles or len(candles) < 20:
            return Signal(
                symbol=symbol, direction=SignalDirection.NEUTRAL, score=0.0,
                confidence=0.0, technical_score=0.0, price_action_score=0.0,
                news_score=0.0, components=[], current_price=current_price,
                time_horizon="1h", entry_point=current_price, take_profit=0.0,
                stop_loss=0.0, risk_reward_ratio=0.0,
            )

        indicators = TechnicalIndicators.calculate_all(candles, period=14)
        if not indicators:
            return Signal(
                symbol=symbol, direction=SignalDirection.NEUTRAL, score=0.0,
                confidence=0.0, technical_score=0.0, price_action_score=0.0,
                news_score=0.0, components=[], current_price=current_price,
                time_horizon="1h", entry_point=current_price, take_profit=0.0,
                stop_loss=0.0, risk_reward_ratio=0.0,
            )

        indicators["_closes"] = [c["close"] for c in candles]

        # ── Multi-timeframe: fetch daily candles for higher-TF trend ──
        htf_bias = 0.0
        try:
            async with _api_semaphore:
                htf_candles = await asyncio.wait_for(
                    asyncio.to_thread(data_provider.get_candles, symbol, "D", 60),
                    timeout=10.0
                )
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

        # ── Volatility filter ──
        atr = indicators.get("atr_14", current_price * 0.01)
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
        if atr_pct > 3.0:
            # Return neutral but with price
            return Signal(
                symbol=symbol, direction=SignalDirection.NEUTRAL, score=0.0,
                confidence=0.0, technical_score=0.0, price_action_score=0.0,
                news_score=0.0, components=[], current_price=current_price,
                time_horizon="1h", entry_point=current_price, take_profit=0.0,
                stop_loss=0.0, risk_reward_ratio=0.0,
            )

        # ── News sentiment ──
        news_score = 0.0
        try:
            async with _api_semaphore:
                news = await asyncio.wait_for(
                    news_client_instance.get_news(symbol, 5),
                    timeout=8.0
                )
            if news and len(news) > 0:
                sentiments = [article.get('sentiment', 0) for article in news]
                news_score = sum(sentiments) / len(sentiments) if sentiments else 0
        except Exception:
            pass  # News is optional

        # ── Run selected strategy ──
        strategy_id = get_symbol_strategy(symbol)
        strategy = get_strategy(strategy_id)
        indicators["_closes"] = [c["close"] for c in candles]

        result = strategy.score(
            candles=candles, indicators=indicators, symbol=symbol,
            instrument_info=info, current_price=current_price,
            htf_bias=htf_bias, news_score=news_score,
        )

        signal = Signal(
            symbol=symbol,
            direction=result["direction"],
            score=result["score"],
            confidence=result["confidence"],
            technical_score=result["technical_score"],
            price_action_score=0.0,
            news_score=news_score,
            components=result["components"],
            current_price=current_price,
            time_horizon="1h",
            entry_point=current_price,
            take_profit=result["take_profit"],
            stop_loss=result["stop_loss"],
            risk_reward_ratio=result["risk_reward_ratio"],
        )
        
        return signal

    except Exception as e:
        log_event(f"Error analyzing {symbol}: {e}", "error")
        return Signal(
            symbol=symbol, direction=SignalDirection.NEUTRAL, score=0.0,
            confidence=0.0, technical_score=0.0, price_action_score=0.0,
            news_score=0.0, components=[], current_price=0.0,
            time_horizon="1h", entry_point=0.0, take_profit=0.0,
            stop_loss=0.0, risk_reward_ratio=0.0,
        )


@async_timed("generate_signals")
async def generate_signals() -> List[Signal]:
    """Generate trading signals for all instruments using regime-adaptive scoring - PARALLEL"""
    global alpha_client, account

    account["last_scan"] = datetime.utcnow().isoformat()

    # Track peak balance for drawdown calculation
    if account["balance_pln"] > account.get("peak_balance_pln", INITIAL_BALANCE_PLN):
        account["peak_balance_pln"] = account["balance_pln"]

    news_client_instance = get_news_client()

    # Run all symbol analysis in PARALLEL
    tasks = [
        _analyze_single_symbol(symbol, info, news_client_instance)
        for symbol, info in INSTRUMENTS.items()
    ]
    signals = await asyncio.gather(*tasks)

    # Log results
    # Log results
    for signal in signals:
        if signal.direction != SignalDirection.NEUTRAL:
            log_event(f"[SIGNAL] {signal.symbol}: {signal.direction.value} | Score: {signal.score:.2f} | Conf: {signal.confidence:.0%} | ${signal.current_price:.2f}", "event")
    
    # Update equity after signals
    update_account_equity()
    
    return signals

# =====================
# AUTO-TRADING ENGINE
# =====================

AUTO_TRADE_INTERVAL_SEC = 300  # Scan every 5 minutes
AUTO_TRADE_ENABLED = True     # Master switch — can be toggled via API (disabled until async-signals ready)
_trading_task = None           # Reference to the background task

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

    while True:
        try:
            if not AUTO_TRADE_ENABLED:
                await asyncio.sleep(AUTO_TRADE_INTERVAL_SEC)
                continue

            # ── Step 1: Update prices & auto-close TP/SL ──
            auto_closed = broker.update_prices(data_provider)
            if auto_closed:
                for closed in auto_closed:
                    pos = closed.get("position", {})
                    reason = closed.get("exit_reason", "TP/SL")
                    pnl = pos.get("pnl_usd", 0)
                    sym = pos.get("symbol", "?")
                    log_event(
                        f"[AUTO-CLOSE] {sym} {pos.get('direction', '').upper()} hit {reason} "
                        f"| P&L: {'+'if pnl>=0 else ''}{pnl:.2f} USD",
                        "success" if pnl >= 0 else "warning"
                    )
                await async_save_account(account)

            # ── Step 2: Generate fresh signals ──
            signals = await generate_signals()

            # ── Step 3: Auto-execute trades on strong signals ──
            can_trade, reason = check_circuit_breaker()
            if can_trade:
                for signal in signals:
                    if signal.direction in (SignalDirection.NEUTRAL,):
                        continue

                    sym = signal.symbol
                    info = INSTRUMENTS.get(sym, {})
                    min_score = info.get("min_score", 0.15)

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
                    already_open = any(
                        p["symbol"] == sym and p["direction"] == direction
                        for p in open_positions
                    )
                    if already_open:
                        continue

                    # Calculate position size and open trade
                    entry_price = signal.entry_point
                    size = calculate_position_size(sym, entry_price, signal.stop_loss)

                    result = broker.open_position(
                        symbol=sym, direction=direction, size=size,
                        take_profit=signal.take_profit, stop_loss=signal.stop_loss,
                        entry_price=entry_price,
                    )
                    if "error" not in result:
                        log_event(
                            f"[AUTO-TRADE] Opened {direction.upper()} {sym} @ {entry_price:.2f} "
                            f"| Score: {signal.score:.3f} | SL: {signal.stop_loss:.2f} TP: {signal.take_profit:.2f}",
                            "success"
                        )
                    else:
                        log_event(f"[AUTO-TRADE] Failed to open {sym}: {result['error']}", "warning")
            else:
                log_event(f"[AUTO-TRADE] Skipping: {reason}", "info")

            # ── Step 4: Persist state ──
            await async_save_account(account)
            await async_save_signal_cache_db(signal_history_cache)

            log_event(
                f"[AUTO-TRADE] Scan complete | Balance: {account['balance_pln']:.2f} PLN "
                f"| Open: {len(open_positions)} | Closed: {len(closed_positions)}",
                "info"
            )

        except Exception as e:
            log_event(f"[AUTO-TRADE] Error in trading loop: {str(e)}", "error")

        await asyncio.sleep(AUTO_TRADE_INTERVAL_SEC)


@app.get("/api/auto-trade")
async def get_auto_trade_status():
    """Get auto-trading status."""
    return {
        "enabled": AUTO_TRADE_ENABLED,
        "interval_sec": AUTO_TRADE_INTERVAL_SEC,
        "last_scan": account.get("last_scan"),
        "open_positions": len(open_positions),
    }

@app.post("/api/auto-trade")
async def set_auto_trade(enabled: bool):
    """Enable/disable auto-trading."""
    global AUTO_TRADE_ENABLED
    AUTO_TRADE_ENABLED = enabled
    log_event(f"[AUTO-TRADE] {'ENABLED' if enabled else 'DISABLED'}", "event")
    return {"enabled": AUTO_TRADE_ENABLED}

@app.post("/api/auto-trade/interval")
async def set_auto_trade_interval(seconds: int):
    """Set auto-trade scan interval (min 60s, max 3600s)."""
    global AUTO_TRADE_INTERVAL_SEC
    if seconds < 60 or seconds > 3600:
        return {"error": "Interval must be between 60 and 3600 seconds"}
    AUTO_TRADE_INTERVAL_SEC = seconds
    log_event(f"[AUTO-TRADE] Interval set to {seconds}s", "event")
    return {"interval_sec": AUTO_TRADE_INTERVAL_SEC}



@app.get("/")
async def root():
    return {"message": "CFD Trading Bot API", "status": "running", "version": "0.2.0"}

@app.get("/health")
async def health():
    """Health check with MongoDB status"""
    mongo_status = "connected" if db.is_connected() else "disconnected"
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "mongodb": mongo_status,
        "version": "0.2.0"
    }

@app.get("/api/timing-report")
async def get_timing_report():
    """Get performance timing report for all profiled functions."""
    report = {}
    for name, stats in _timing_stats.items():
        if stats["calls"] > 0:
            report[name] = {
                "calls": stats["calls"],
                "total_sec": round(stats["total"], 3),
                "avg_sec": round(stats["total"] / stats["calls"], 3),
                "min_sec": round(stats["min"], 3),
                "max_sec": round(stats["max"], 3),
            }
    # Sort by total time (descending)
    report = dict(sorted(report.items(), key=lambda x: -x[1]["total_sec"]))
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "functions": report,
        "count": len(report)
    }

@app.delete("/api/timing-report")
async def clear_timing_report():
    """Clear timing statistics."""
    _timing_stats.clear()
    return {"status": "cleared"}

@app.get("/api/status")
async def get_status():
    """Detailed status endpoint for debugging"""
    mongo_uri_set = bool(os.getenv("MONGO_URI") or os.getenv("MONGODB_URI"))
    mongo_connected = db.is_connected()
    
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.2.0",
        "environment": {
            "mongo_uri_set": mongo_uri_set,
            "mongo_db": os.getenv("MONGO_DB", "cfd_trading_bot"),
            "mongo_connected": mongo_connected,
            "broker_type": os.getenv("BROKER_TYPE", "sim"),
        },
        "account": {
            "balance_pln": account.get("balance_pln", 0),
            "equity_pln": account.get("equity_pln", 0),
            "open_trades": len(open_positions),
            "mode": account.get("mode", "simulate"),
        },
        "instruments": list(INSTRUMENTS.keys()),
    }

@app.get("/api/signals", response_model=SignalResponse)
@async_timed("get_signals_endpoint")
async def get_signals():
    """Fetch real trading signals"""
    log_event("Generating signals...", "info")
    signals = await generate_signals()
    return SignalResponse(signals=signals)

@app.get("/api/logs")
async def get_logs():
    return {"logs": event_log}

@app.get("/api/account")
async def get_account():
    """Get account info with PLN balance"""
    update_account_equity()
    # Add initial_balance_pln to response for frontend calculations
    return {**account, "initial_balance_pln": INITIAL_BALANCE_PLN}

@app.post("/api/account/mode")
async def set_account_mode(mode: str):
    global account
    if mode not in ["simulate", "live"]:
        return {"error": "Invalid mode. Use 'simulate' or 'live'"}
    account["mode"] = mode
    account["dry_run"] = (mode == "simulate")
    await async_save_account(account)
    log_event(f"Trading mode changed to: {mode.upper()}", "event")
    return {"mode": account["mode"], "dry_run": account["dry_run"]}

# =====================
# INSTRUMENT SETTINGS
# =====================

@app.get("/api/instruments")
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
        }
        for symbol, info in INSTRUMENTS.items()
    }

@app.post("/api/instruments/{symbol}/leverage")
async def set_leverage(symbol: str, leverage: int):
    """Update leverage for an instrument. Valid values: 1-100."""
    if symbol not in INSTRUMENTS:
        return {"error": f"Unknown instrument: {symbol}"}
    if leverage < 1 or leverage > 100:
        return {"error": "Leverage must be between 1 and 100"}
    INSTRUMENTS[symbol]["leverage"] = leverage
    log_event(f"[SETTINGS] {symbol} leverage set to x{leverage}", "event")
    return {"symbol": symbol, "leverage": leverage}

@app.post("/api/instruments/{symbol}/trailing_stop")
async def set_trailing_stop(symbol: str, enabled: bool):
    """Enable/disable trailing stop for an instrument."""
    if symbol not in INSTRUMENTS:
        return {"error": f"Unknown instrument: {symbol}"}
    INSTRUMENTS[symbol]["trailing_stop"] = enabled
    log_event(f"[SETTINGS] {symbol} trailing stop {'enabled' if enabled else 'disabled'}", "event")
    return {"symbol": symbol, "trailing_stop": enabled}

# =====================
# STRATEGY SELECTION
# =====================

@app.get("/api/strategies")
async def get_strategies():
    """List all available trading strategies."""
    return {"strategies": list_strategies()}

@app.get("/api/strategy/{symbol}")
async def get_strategy_for_symbol(symbol: str):
    """Get the active strategy for a symbol."""
    return {"symbol": symbol, "strategy": get_symbol_strategy(symbol)}

@app.post("/api/strategy/{symbol}")
async def set_strategy_for_symbol(symbol: str, strategy_id: str):
    """Set the active strategy for a symbol."""
    from strategies import STRATEGIES
    if strategy_id not in STRATEGIES:
        return {"error": f"Unknown strategy: {strategy_id}. Available: {list(STRATEGIES.keys())}"}
    set_symbol_strategy(symbol, strategy_id)
    log_event(f"[STRATEGY] {symbol} → {STRATEGIES[strategy_id].display_name}", "event")
    return {"symbol": symbol, "strategy": strategy_id}

@app.get("/api/strategy-selection")
async def get_all_strategy_selections():
    """Get strategy selection for all symbols."""
    return {sym: get_symbol_strategy(sym) for sym in INSTRUMENTS}

# =====================
# SIMULATED TRADING API
# =====================

@app.post("/api/trade/open")
async def open_trade(symbol: str, direction: str, size: float = 0):
    """
    Open a simulated trade position.
    size: lot size - if 0, automatically calculated from risk management rules.
    """
    global account

    if symbol not in INSTRUMENTS:
        return {"error": f"Unknown instrument: {symbol}"}
    if direction not in ["buy", "sell"]:
        return {"error": "Direction must be 'buy' or 'sell'"}

    # Circuit breaker check
    can_trade, reason = check_circuit_breaker()
    if not can_trade:
        log_event(f"[BLOCKED] {reason}", "warning")
        return {"error": reason}

    # Check for duplicate position on same symbol+direction
    for pos in open_positions:
        if pos["symbol"] == symbol and pos["direction"] == direction:
            return {"error": f"Already have an open {direction} position on {symbol}"}

    quote = data_provider.get_quote(symbol)
    if not quote:
        return {"error": f"Cannot get price for {symbol}"}

    entry_price = quote["price"]

    # Get signal data for TP/SL
    signal = signals_cache.get(symbol)
    if signal:
        take_profit = signal.take_profit
        stop_loss = signal.stop_loss
    else:
        atr = entry_price * 0.01
        if direction == "buy":
            take_profit = entry_price + (atr * 3)
            stop_loss = entry_price - (atr * 2)
        else:
            take_profit = entry_price - (atr * 3)
            stop_loss = entry_price + (atr * 2)

    if size <= 0:
        size = calculate_position_size(symbol, entry_price, stop_loss)

    result = broker.open_position(
        symbol=symbol, direction=direction, size=size,
        take_profit=take_profit, stop_loss=stop_loss, entry_price=entry_price,
    )
    if "error" in result:
        return result

    log_event(f"[TRADE] Opened {direction.upper()} {symbol} @ {entry_price:.2f} | Size: {size}", "success")
    return result

@app.post("/api/trade/close/{position_id}")
async def close_trade(position_id: str):
    """Close an open trade position via broker"""
    # Get current price for the position
    position = next((p for p in open_positions if p["id"] == position_id), None)
    if not position:
        return {"error": f"Position {position_id} not found"}

    quote = data_provider.get_quote(position["symbol"])
    exit_price = quote["price"] if quote else None

    result = broker.close_position(position_id, exit_price=exit_price)
    if "error" in result:
        return result

    closed_pos = result["position"]
    pnl_pln = closed_pos.get("pnl_pln", 0)
    pnl_usd = closed_pos.get("pnl_usd", 0)
    emoji = "+" if pnl_usd >= 0 else ""
    log_event(
        f"[TRADE] Closed {position['direction'].upper()} {position['symbol']} @ {exit_price:.2f} | P&L: {emoji}{pnl_pln:.2f} PLN ({emoji}{pnl_usd:.2f} USD)",
        "success" if pnl_usd >= 0 else "warning"
    )

    update_account_equity()
    return result

@app.get("/api/trades/open")
async def get_open_trades():
    """Get all open positions with live P&L - always from DB for consistency"""
    update_account_equity()
    # Load from DB to ensure we have data after restart
    db_positions = await async_load_open_positions()
    # Merge with in-memory (in-memory may have newer updates)
    position_map = {p["id"]: p for p in db_positions}
    for p in open_positions:
        position_map[p["id"]] = p  # In-memory wins (newer)
    merged = list(position_map.values())
    return {"positions": merged, "count": len(merged)}

@app.get("/api/trades/history")
async def get_trade_history(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    """Get closed trade history - always from DB for consistency"""
    # Always query DB - don't rely on in-memory cache that clears on restart
    trades = await async_load_closed_positions(limit=limit + offset)
    trades = trades[offset:offset + limit] if offset < len(trades) else []
    
    total_in_db = await async_count_closed_positions()

    return {
        "trades": trades,
        "total": total_in_db,
        "offset": offset,
        "win_count": account["win_count"],
        "loss_count": account["loss_count"],
        "win_rate": account["win_rate"],
        "total_pnl_pln": account["total_pnl_pln"],
        "total_pnl_usd": account["total_pnl_usd"]
    }

@app.post("/api/account/reset")
async def reset_account():
    """Reset simulated account to starting balance"""
    if not hasattr(broker, 'reset'):
        return {"error": "Reset not supported for live brokers"}
    result = broker.reset()
    log_event("[ACCOUNT] Reset to 10,000.00 PLN", "event")
    return {"status": "reset", "account": account}

# =====================
# NEWS & CHART ENDPOINTS
# =====================

@app.get("/api/news/all")
async def get_all_news():
    """Get latest news for all symbols (with rate limiting)"""
    log_event("Fetching news for all symbols...", "info")
    news_client = get_news_client()
    all_news = []

    for i, (symbol, info) in enumerate(INSTRUMENTS.items()):
        try:
            news = await news_client.get_news(symbol, limit=5)
            if news:
                for article in news:
                    article["symbol"] = symbol
                    article["name"] = info["name"]
                all_news.extend(news)
            # Rate limit: 12s delay to stay under 5 req/min (Alpha Vantage free tier)
            if i < len(INSTRUMENTS) - 1:
                await asyncio.sleep(12)
        except Exception as e:
            log_event(f"Failed to scrape news for {symbol}: {e}", "error")

    all_news.sort(key=lambda x: x.get("importance", 0), reverse=True)
    return {"news": all_news, "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/news/{symbol}")
async def get_news(symbol: str):
    news_client = get_news_client()
    try:
        news = await news_client.get_news(symbol, limit=5)
        return {"symbol": symbol, "news": news or [], "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"symbol": symbol, "news": [], "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    global alpha_client
    if alpha_client is None:
        alpha_client = get_alpha_vantage_client()
    quote = alpha_client.get_quote(symbol)
    return quote if quote else {"error": f"Failed to fetch quote for {symbol}"}

@app.get("/api/chart/{symbol}")
@async_timed("get_chart_data")
async def get_chart_data(symbol: str, resolution: str = "60", count: int = 100):
    """
    Get historical chart data for a symbol.
    FAST: Uses DB/cache first, only fetches fresh data if stale.
    Includes ISO timestamps for proper session/time mapping.
    """
    global alpha_client
    if alpha_client is None:
        alpha_client = get_alpha_vantage_client()

    WARMUP = 60  # extra candles for SMA50 + MACD warmup
    fetch_count = count + WARMUP
    fetched_at = datetime.utcnow().isoformat()

    def _format_candles(candles):
        chart_data = []
        for candle in candles:
            timestamp = candle.get("timestamp", "")
            time_str = candle.get("time", "")
            if not time_str and timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime('%m/%d') if resolution == 'D' else dt.strftime('%H:%M')
                except Exception:
                    time_str = timestamp[:5] if len(timestamp) >= 5 else timestamp
            chart_data.append({
                "time": time_str,
                "timestamp": timestamp,
                "close": round(candle["close"], 2),
                "open": round(candle["open"], 2),
                "high": round(candle["high"], 2),
                "low": round(candle["low"], 2),
                "volume": candle.get("volume", 0)
            })
        return chart_data

    # 1. FAST PATH: Check DB/cache first (instant response)
    candle_map = {}
    db_candles = await async_load_candle_history(symbol, resolution, limit=fetch_count * 2)
    for c in db_candles:
        ts = c.get("timestamp", "")
        if ts:
            candle_map[ts] = c
    
    # Check if cache is fresh (less than 5 minutes old)
    cache_is_fresh = False
    if db_candles:
        latest_ts = db_candles[-1].get("timestamp", "")
        if latest_ts:
            try:
                latest_dt = datetime.fromisoformat(latest_ts.replace('Z', '+00:00'))
                cache_age = (datetime.utcnow() - latest_dt).total_seconds()
                cache_is_fresh = cache_age < 300  # 5 minutes
            except:
                pass

    fresh_candles = []
    source = "db" if candle_map else "none"

    # 2. Only fetch fresh data if cache is stale or empty
    if not cache_is_fresh or len(candle_map) < 20:
        # Try Alpha Vantage in background
        try:
            candles = await asyncio.wait_for(
                asyncio.to_thread(alpha_client.get_candles, symbol, resolution, fetch_count),
                timeout=3.0  # Quick timeout - don't wait too long
            )
            if candles and len(candles) > 0:
                fresh_candles = candles
                source = "alpha_vantage"
                # Store in background - don't wait
                asyncio.create_task(async_store_candles(symbol, resolution, candles, "alpha_vantage"))
        except Exception as e:
            log_event(f"Alpha Vantage chart fetch failed for {symbol}: {e}", "debug")

        # 3. Yahoo Finance fallback (if Alpha Vantage failed)
        if not fresh_candles:
            try:
                yahoo_interval = {"1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "1h", "D": "1d"}.get(resolution, "1h")
                period = 30 if resolution in ("1", "5", "15", "30", "60") else 365
                from historical_data import fetch_yahoo_historical
                candles = await asyncio.wait_for(
                    asyncio.to_thread(fetch_yahoo_historical, symbol, period_days=period, interval=yahoo_interval),
                    timeout=5.0
                )
                if candles and len(candles) > 0:
                    fresh_candles = candles
                    source = "yahoo"
                    asyncio.create_task(async_store_candles(symbol, resolution, candles, "yahoo"))
            except Exception as e:
                log_event(f"Yahoo chart fetch failed for {symbol}: {e}", "debug")

    # 5. Merge fresh data with DB (fresh wins)
    for c in fresh_candles:
        ts = c.get("timestamp", "")
        if ts:
            candle_map[ts] = c

    # 6. Aggregation fallback if still insufficient
    if len(candle_map) < 20:
        source_candidates = {"5": ["1"], "15": ["5", "1"], "30": ["15", "5"], "60": ["30", "15", "5"], "D": ["60", "30"]}
        for src_res in source_candidates.get(resolution, []):
            stored = await async_load_candle_history(symbol, src_res)
            if stored and len(stored) >= 10:
                aggregated = db.aggregate_candles(stored, resolution)
                for c in aggregated:
                    ts = c.get("timestamp", "")
                    if ts and ts not in candle_map:
                        candle_map[ts] = c
                if len(candle_map) >= 20:
                    source = source or "aggregated"
                    break

    if not candle_map:
        # Last resort: candle_cache
        cached = await async_load_candles(symbol, resolution)
        if cached and cached.get("candles"):
            return {
                "symbol": symbol, "data": cached["candles"], "resolution": resolution,
                "count": len(cached["candles"]), "source": "cache",
                "fetched_at": cached.get("fetched_at", fetched_at),
            }
        return {"error": f"No real data available for {symbol}. Check API key or try again later."}

    # Sort chronologically, take last fetch_count
    all_candles = sorted(candle_map.values(), key=lambda c: c.get("timestamp", ""))
    all_candles = all_candles[-fetch_count:]

    chart_data = _format_candles(all_candles)

    # Update candle_cache for backward compat
    await async_save_candles(symbol, resolution, chart_data, source or "hybrid")

    return {
        "symbol": symbol, "data": chart_data, "resolution": resolution,
        "count": len(chart_data), "source": source or "hybrid",
        "fetched_at": fetched_at,
    }

# Alert Endpoints
@app.get("/api/alerts/config")
async def get_alert_config():
    dispatcher = get_dispatcher()
    return dispatcher.config.dict()

@app.post("/api/alerts/config")
async def update_alert_config(config: AlertConfig):
    dispatcher = get_dispatcher()
    dispatcher.update_config(config)
    return {"status": "updated", "config": dispatcher.config.dict()}

@app.post("/api/alerts/test")
async def send_test_alert():
    dispatcher = get_dispatcher()
    if not dispatcher.config.enabled:
        return {"status": "error", "message": "Alerts are disabled"}
    try:
        result = dispatcher.send_alert(
            symbol="TEST", direction="buy", score=0.8, confidence=0.85,
            current_price=50000.0, entry_point=49500.0, take_profit=51000.0, stop_loss=49000.0
        )
        if result["status"] == "sent":
            return {"status": "sent", "message_id": result.get("message_id")}
        return {"status": "error", "message": result.get("error", "Failed")}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/alerts/history")
async def get_alert_history(symbol: Optional[str] = None, limit: int = Query(20, ge=1, le=100)):
    dispatcher = get_dispatcher()
    history = dispatcher.get_alert_history(symbol=symbol, limit=limit)
    return {"history": history, "total": len(history), "symbol_filter": symbol}

@app.delete("/api/alerts/history")
async def clear_alert_history():
    dispatcher = get_dispatcher()
    dispatcher.clear_history()
    return {"status": "cleared"}

# =====================
# CANDLE HISTORY
# =====================

@app.get("/api/candles/stats")
async def get_candle_stats():
    """Get stored candle history statistics for all instruments."""
    stats = {}
    resolutions = ["1", "5", "15", "30", "60", "D"]
    for symbol in INSTRUMENTS:
        symbol_stats = {}
        for res in resolutions:
            cnt = await async_count_candles(symbol, res)
            if cnt > 0:
                date_range = await async_get_candle_date_range(symbol, res)
                symbol_stats[res] = {"count": cnt, "range": date_range}
        if symbol_stats:
            stats[symbol] = symbol_stats
    return {"stats": stats}


@app.get("/api/candles/{symbol}")
@async_timed("get_candle_history")
async def get_candle_history(
    symbol: str,
    resolution: str = "60",
    count: int = Query(100, ge=1, le=5000),
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """
    Get stored candle history for a symbol.
    Supports aggregation: request any resolution and it will be built from
    the smallest available stored interval.
    """
    # Direct fetch from accumulated history
    candles = await async_load_candle_history(symbol, resolution, start=start, end=end, limit=count)

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
            stored = await async_load_candle_history(symbol, src_res, start=start, end=end)
            if stored and len(stored) >= 2:
                aggregated = db.aggregate_candles(stored, resolution)
                if len(aggregated) > len(candles):
                    candles = aggregated[-count:]
                    break

    return {
        "symbol": symbol,
        "resolution": resolution,
        "count": len(candles),
        "candles": candles,
    }


# =====================
# SERVE FRONTEND (production)
# =====================
# In production, the backend serves the built frontend as static files.
# Build with: cd frontend && npm run build
# The dist/ folder is served at / and all non-API routes fall back to index.html (SPA)

import pathlib
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_frontend_dist = pathlib.Path(__file__).parent.parent / "frontend" / "dist"

if _frontend_dist.is_dir():
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend SPA – all non-API routes get index.html"""
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
