"""
CFD Trading Bot - FastAPI Backend
Real-time signal generation using Finnhub data and technical indicators
Simulated trading engine with PLN currency
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import uvicorn
import asyncio
from typing import List, Optional
import os
import json
import uuid
from dotenv import load_dotenv

from models import Signal, SignalDirection, Component, ComponentType, SignalResponse
from alpha_vantage import get_client as get_alpha_vantage_client
from alpha_vantage_news import get_client as get_news_client
from realistic_prices import get_feeder as get_realistic_price_feeder
from indicators import TechnicalIndicators
from imessage_alerts import AlertConfig, iMessageAlertDispatcher, get_dispatcher
from openclaw_integration import set_openclaw_message_function, format_imessage_for_cfd_alert
import database as db

load_dotenv()

app = FastAPI(
    title="CFD Trading Bot API",
    description="Real-time trading signals for CFD instruments with simulated trading",
    version="0.2.0"
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
event_log = []

# Account and trade state – loaded from MongoDB on startup, falls back to defaults
account = db.load_account()
open_positions = db.load_open_positions()
closed_positions = db.load_closed_positions()

# Signal history cache for trend analysis
signal_history_cache = {}

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

# Instruments to monitor
INSTRUMENTS = {
    "XAU": {"name": "Gold", "multiplier": 1, "pip_size": 0.01, "lot_size": 1},
    "XAG": {"name": "Silver", "multiplier": 1, "pip_size": 0.001, "lot_size": 100},
    "US100": {"name": "Nasdaq-100", "multiplier": 1, "pip_size": 0.01, "lot_size": 1},
    "BTC": {"name": "Bitcoin", "multiplier": 1, "pip_size": 1.0, "lot_size": 0.01}
}

def log_event(message: str, log_type: str = "info"):
    """Log events for the console"""
    event_log.append({
        "id": str(len(event_log)),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "message": message,
        "type": log_type
    })
    if len(event_log) > 100:
        event_log.pop(0)
    print(f"[{log_type.upper()}] {message}")

def calculate_signal_score(indicators: dict, symbol: str = "") -> tuple[float, List[Component]]:
    """
    Enhanced composite signal scoring with multi-factor weighted system.
    Uses RSI, MACD, Momentum, Bollinger Bands, SMA crossover.
    Returns score (-1 to +1) and components breakdown.
    """
    components = []
    scores = []
    weights = []

    # --- RSI Component (weight: 25%) ---
    if indicators.get("rsi_14") is not None:
        rsi = indicators["rsi_14"]
        if rsi < 30:
            rsi_score = -((30 - rsi) / 30)  # Oversold = bearish pressure
        elif rsi > 70:
            rsi_score = (rsi - 70) / 30      # Overbought = bullish pressure
        else:
            rsi_score = (rsi - 50) / 50       # Neutral zone
        rsi_score = max(-1, min(1, rsi_score))

        zone = "OVERSOLD" if rsi < 30 else "OVERBOUGHT" if rsi > 70 else "NEUTRAL"
        components.append(Component(
            type=ComponentType.TECHNICAL,
            name="RSI (14)",
            value=rsi_score,
            description=f"RSI at {rsi:.1f} ({zone})",
            confidence=0.85 if abs(rsi - 50) > 20 else 0.6,
            indicators={"value": rsi, "zone": zone}
        ))
        scores.append(rsi_score)
        weights.append(0.25)

    # --- MACD Component (weight: 25%) ---
    if indicators.get("macd"):
        macd = indicators["macd"]
        if macd.get("histogram") is not None and macd.get("macd_line") is not None:
            histogram = macd["histogram"]
            macd_line = macd["macd_line"]
            signal_line = macd.get("signal_line", 0) or 0

            # Histogram direction and crossover
            if histogram > 0 and macd_line > signal_line:
                macd_score = min(1, histogram / max(abs(macd_line), 0.01) * 2)
            elif histogram < 0 and macd_line < signal_line:
                macd_score = max(-1, histogram / max(abs(macd_line), 0.01) * 2)
            else:
                macd_score = max(-1, min(1, histogram / 100)) if histogram != 0 else 0

            cross = "BULLISH_CROSS" if macd_line > signal_line else "BEARISH_CROSS"
            components.append(Component(
                type=ComponentType.TECHNICAL,
                name="MACD",
                value=macd_score,
                description=f"MACD hist: {histogram:.4f} ({cross})",
                confidence=0.8 if abs(histogram) > 0.5 else 0.55,
                indicators=macd
            ))
            scores.append(macd_score)
            weights.append(0.25)

    # --- Momentum Component (weight: 15%) ---
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
            confidence=0.7,
            indicators={"value": momentum, "pct": mom_pct}
        ))
        scores.append(momentum_score)
        weights.append(0.15)

    # --- Bollinger Bands Component (weight: 20%) ---
    if indicators.get("bollinger_bands"):
        bb = indicators["bollinger_bands"]
        closes = indicators.get("_closes", [])
        if closes:
            current_price = closes[-1]
            bb_upper = bb["upper"]
            bb_lower = bb["lower"]
            bb_middle = bb["middle"]
            bb_range = bb_upper - bb_lower if bb_upper != bb_lower else 1

            # Position within bands (-1 = at lower, +1 = at upper)
            bb_position = ((current_price - bb_lower) / bb_range) * 2 - 1
            # Near upper band = overbought (sell), near lower = oversold (buy)
            bb_score = -bb_position * 0.8  # Reverse: near upper = sell signal

            zone = "UPPER" if current_price > bb_upper else "LOWER" if current_price < bb_lower else "MIDDLE"
            components.append(Component(
                type=ComponentType.TECHNICAL,
                name="Bollinger Bands",
                value=max(-1, min(1, bb_score)),
                description=f"BB position: {zone} ({bb_position:.2f})",
                confidence=0.75 if abs(bb_position) > 0.8 else 0.5,
                indicators={"position": bb_position, "zone": zone}
            ))
            scores.append(max(-1, min(1, bb_score)))
            weights.append(0.20)

    # --- SMA Crossover Component (weight: 15%) ---
    if indicators.get("sma_20") is not None and indicators.get("sma_50") is not None:
        sma_20 = indicators["sma_20"]
        sma_50 = indicators["sma_50"]
        if sma_50 > 0:
            sma_diff_pct = ((sma_20 - sma_50) / sma_50) * 100
            sma_score = max(-1, min(1, sma_diff_pct / 2))

            trend = "BULLISH" if sma_20 > sma_50 else "BEARISH"
            components.append(Component(
                type=ComponentType.TECHNICAL,
                name="SMA Cross (20/50)",
                value=sma_score,
                description=f"SMA20 vs SMA50: {sma_diff_pct:.2f}% ({trend})",
                confidence=0.7,
                indicators={"sma_20": sma_20, "sma_50": sma_50, "trend": trend}
            ))
            scores.append(sma_score)
            weights.append(0.15)

    # Calculate weighted composite score
    if scores:
        total_weight = sum(weights)
        composite_score = sum(s * w for s, w in zip(scores, weights)) / total_weight if total_weight > 0 else 0
    else:
        composite_score = 0

    return composite_score, components

def calculate_trend_score(current_score: float, previous_scores: List[float]) -> float:
    """Calculate trend-based score adjustment based on previous signal scores"""
    if not previous_scores or len(previous_scores) < 2:
        return 0.0

    recent_scores = previous_scores[-5:]
    if len(recent_scores) < 2:
        return 0.0

    score_changes = [recent_scores[i] - recent_scores[i-1] for i in range(1, len(recent_scores))]
    avg_change = sum(score_changes) / len(score_changes)

    positive_changes = sum(1 for change in score_changes if change > 0)
    negative_changes = sum(1 for change in score_changes if change < 0)
    consistency = abs(positive_changes - negative_changes) / len(score_changes)

    trend_bonus = avg_change * consistency * 0.2
    recent_avg = sum(recent_scores) / len(recent_scores)
    deviation = abs(current_score - recent_avg)
    mean_reversion_penalty = -deviation * 0.1 if deviation > 0.3 else 0.0

    return trend_bonus + mean_reversion_penalty

def get_signal_direction(score: float) -> SignalDirection:
    """Determine signal direction from score"""
    if score > 0.6:
        return SignalDirection.STRONG_BUY
    elif score > 0.2:
        return SignalDirection.BUY
    elif score < -0.6:
        return SignalDirection.STRONG_SELL
    elif score < -0.2:
        return SignalDirection.SELL
    else:
        return SignalDirection.NEUTRAL

def update_account_equity():
    """Update account equity based on open positions"""
    global account
    price_feeder = get_realistic_price_feeder()
    unrealized_pnl_usd = 0.0

    for pos in open_positions:
        quote = price_feeder.get_quote(pos["symbol"])
        if quote:
            current_price = quote["price"]
            if pos["direction"] == "buy":
                pnl = (current_price - pos["entry_price"]) * pos["size"]
            else:
                pnl = (pos["entry_price"] - current_price) * pos["size"]
            pos["current_price"] = current_price
            pos["unrealized_pnl_usd"] = round(pnl, 2)
            pos["unrealized_pnl_pln"] = round(pnl * PLN_USD_RATE, 2)
            unrealized_pnl_usd += pnl

    unrealized_pnl_pln = unrealized_pnl_usd * PLN_USD_RATE
    account["equity_pln"] = round(account["balance_pln"] + unrealized_pnl_pln, 2)
    account["equity_usd"] = round(account["equity_pln"] / PLN_USD_RATE, 2)
    account["open_trades"] = len(open_positions)
    account["positions"] = len(open_positions)

async def generate_signals() -> List[Signal]:
    """Generate trading signals for all instruments"""
    global alpha_client, account

    account["last_scan"] = datetime.utcnow().isoformat()

    price_feeder = get_realistic_price_feeder()
    news_client_instance = get_news_client()

    signals = []

    for symbol, info in INSTRUMENTS.items():
        try:
            log_event(f"Analyzing {symbol} ({info['name']})...")

            quote = price_feeder.get_quote(symbol)
            if not quote:
                log_event(f"Failed to generate price for {symbol}", "error")
                continue

            current_price = quote["price"]

            candles = price_feeder.get_candles(symbol, resolution="60", count=100)
            if not candles or len(candles) < 26:
                log_event(f"Insufficient candle data for {symbol}", "error")
                continue

            indicators = TechnicalIndicators.calculate_all(candles, period=14)
            if not indicators:
                log_event(f"Failed to calculate indicators for {symbol}", "warning")
                continue

            # Pass closes for BB calculation
            indicators["_closes"] = [c["close"] for c in candles]

            # Fetch news sentiment
            news_score = 0.0
            try:
                news = await news_client_instance.get_news(symbol, limit=5)
                if news and len(news) > 0:
                    sentiments = [article.get('sentiment', 0) for article in news]
                    news_score = sum(sentiments) / len(sentiments) if sentiments else 0
                    log_event(f"News sentiment for {symbol}: {news_score:.2f} ({len(news)} articles)")
            except Exception as e:
                log_event(f"Failed to fetch news for {symbol}: {e}", "warning")

            # Enhanced scoring
            technical_score, components = calculate_signal_score(indicators, symbol)

            previous_scores = signal_history_cache.get(symbol, [])
            trend_adjustment = calculate_trend_score(technical_score, previous_scores)
            adjusted_technical_score = max(-1, min(1, technical_score + trend_adjustment))

            effective_news_score = news_score if abs(news_score) > 0.1 else 0.0

            # Weighted: 55% technical (improved), 5% price action, 40% news
            score = (adjusted_technical_score * 0.55) + (0 * 0.05) + (effective_news_score * 0.40)
            score = max(-1, min(1, score))

            direction = get_signal_direction(score)

            if symbol not in signal_history_cache:
                signal_history_cache[symbol] = []
            signal_history_cache[symbol].append(score)
            if len(signal_history_cache[symbol]) > 10:
                signal_history_cache[symbol].pop(0)

            if len(signals) % 5 == 0:
                save_signal_cache()

            base_confidence = min(0.95, abs(score) + 0.3)
            if (effective_news_score > 0 and adjusted_technical_score > 0) or \
               (effective_news_score < 0 and adjusted_technical_score < 0):
                confidence = min(0.95, base_confidence * 1.1)
            else:
                confidence = base_confidence

            rsi = indicators.get("rsi_14", 50)
            atr = indicators.get("atr_14", current_price * 0.01)

            entry_point = current_price

            if direction in [SignalDirection.BUY, SignalDirection.STRONG_BUY]:
                stop_loss = entry_point - (atr * 2)
                take_profit = entry_point + (atr * 3)
            else:
                stop_loss = entry_point + (atr * 2)
                take_profit = entry_point - (atr * 3)

            risk = abs(entry_point - stop_loss)
            reward = abs(take_profit - entry_point)
            risk_reward_ratio = reward / risk if risk > 0 else 0

            signal = Signal(
                symbol=symbol,
                direction=direction,
                score=score,
                confidence=confidence,
                technical_score=technical_score,
                price_action_score=0,
                news_score=news_score,
                components=components,
                current_price=current_price,
                time_horizon="1h",
                entry_point=entry_point,
                take_profit=take_profit,
                stop_loss=stop_loss,
                risk_reward_ratio=risk_reward_ratio,
            )

            signals.append(signal)
            signals_cache[symbol] = signal
            log_event(f"[SIGNAL] {symbol}: {direction.value} | Score: {score:.2f} | Conf: {confidence:.0%} | ${current_price:.2f}", "event")

            # Send alert
            try:
                alert_dispatcher = get_dispatcher()
                alert_result = alert_dispatcher.send_alert(
                    symbol=symbol, direction=direction.value, score=score,
                    confidence=confidence, current_price=current_price,
                    entry_point=entry_point, take_profit=take_profit, stop_loss=stop_loss
                )
                if alert_result["status"] == "sent":
                    log_event(f"[ALERT] Sent for {symbol} {direction.value}", "success")
            except Exception as alert_error:
                pass  # Silent alert failures

        except Exception as e:
            log_event(f"Error generating signal for {symbol}: {str(e)}", "error")

    # Update equity after signals
    update_account_equity()

    return signals

@app.on_event("startup")
async def startup():
    """Initialize on startup"""
    log_event("[CFD TRADING BOT v0.2.0 - PLN SIMULATION]", "event")
    log_event("Instruments: XAU (Gold), XAG (Silver), US100 (Nasdaq), BTC (Bitcoin)", "info")

    # Database status
    if db.is_connected():
        log_event("MongoDB connected – trades & account persisted", "success")
        log_event(f"Restored {len(open_positions)} open positions, {len(closed_positions)} closed trades", "info")
    else:
        log_event("MongoDB not configured – using in-memory storage (set MONGO_URI)", "warning")

    global alpha_client
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

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    save_signal_cache()
    db.save_account(account)
    try:
        news_client = get_news_client()
        if hasattr(news_client, 'close'):
            await news_client.close()
    except Exception:
        pass

@app.get("/")
async def root():
    return {"message": "CFD Trading Bot API", "status": "running", "version": "0.2.0"}

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/signals", response_model=SignalResponse)
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
    return account

@app.post("/api/account/mode")
async def set_account_mode(mode: str):
    global account
    if mode not in ["simulate", "live"]:
        return {"error": "Invalid mode. Use 'simulate' or 'live'"}
    account["mode"] = mode
    account["dry_run"] = (mode == "simulate")
    db.save_account(account)
    log_event(f"Trading mode changed to: {mode.upper()}", "event")
    return {"mode": account["mode"], "dry_run": account["dry_run"]}

# =====================
# SIMULATED TRADING API
# =====================

@app.post("/api/trade/open")
async def open_trade(symbol: str, direction: str, size: float = 0.01):
    """
    Open a simulated trade position.
    size: lot size (e.g. 0.01 for micro lot)
    """
    global account

    if symbol not in INSTRUMENTS:
        return {"error": f"Unknown instrument: {symbol}"}
    if direction not in ["buy", "sell"]:
        return {"error": "Direction must be 'buy' or 'sell'"}

    price_feeder = get_realistic_price_feeder()
    quote = price_feeder.get_quote(symbol)
    if not quote:
        return {"error": f"Cannot get price for {symbol}"}

    entry_price = quote["price"]

    # Calculate margin required (simplified: 1% margin for CFDs)
    margin_usd = entry_price * size * 0.01
    margin_pln = margin_usd * PLN_USD_RATE

    if margin_pln > account["available_pln"]:
        return {"error": "Insufficient margin", "required_pln": margin_pln, "available_pln": account["available_pln"]}

    # Get signal data for TP/SL
    signal = signals_cache.get(symbol)
    if signal:
        take_profit = signal.take_profit
        stop_loss = signal.stop_loss
    else:
        atr = entry_price * 0.01  # Default 1% ATR
        if direction == "buy":
            take_profit = entry_price + (atr * 3)
            stop_loss = entry_price - (atr * 2)
        else:
            take_profit = entry_price - (atr * 3)
            stop_loss = entry_price + (atr * 2)

    position = {
        "id": str(uuid.uuid4())[:8],
        "symbol": symbol,
        "name": INSTRUMENTS[symbol]["name"],
        "direction": direction,
        "size": size,
        "entry_price": entry_price,
        "current_price": entry_price,
        "take_profit": round(take_profit, 2),
        "stop_loss": round(stop_loss, 2),
        "margin_pln": round(margin_pln, 2),
        "unrealized_pnl_usd": 0.0,
        "unrealized_pnl_pln": 0.0,
        "opened_at": datetime.utcnow().isoformat(),
        "status": "open"
    }

    open_positions.append(position)
    account["used_margin"] += margin_pln
    account["available_pln"] = account["balance_pln"] - account["used_margin"]
    account["open_trades"] = len(open_positions)
    account["positions"] = len(open_positions)

    # Persist to MongoDB
    db.save_trade(position)
    db.save_account(account)

    log_event(f"[TRADE] Opened {direction.upper()} {symbol} @ {entry_price:.2f} | Size: {size} | Margin: {margin_pln:.2f} PLN", "success")

    return {"status": "opened", "position": position}

@app.post("/api/trade/close/{position_id}")
async def close_trade(position_id: str):
    """Close an open trade position"""
    global account

    position = None
    pos_index = None
    for i, pos in enumerate(open_positions):
        if pos["id"] == position_id:
            position = pos
            pos_index = i
            break

    if not position:
        return {"error": f"Position {position_id} not found"}

    price_feeder = get_realistic_price_feeder()
    quote = price_feeder.get_quote(position["symbol"])
    if not quote:
        return {"error": "Cannot get current price"}

    exit_price = quote["price"]

    # Calculate P&L
    if position["direction"] == "buy":
        pnl_usd = (exit_price - position["entry_price"]) * position["size"]
    else:
        pnl_usd = (position["entry_price"] - exit_price) * position["size"]

    pnl_pln = pnl_usd * PLN_USD_RATE

    # Update account
    account["balance_pln"] = round(account["balance_pln"] + pnl_pln, 2)
    account["balance_usd"] = round(account["balance_pln"] / PLN_USD_RATE, 2)
    account["used_margin"] = max(0, account["used_margin"] - position["margin_pln"])
    account["available_pln"] = account["balance_pln"] - account["used_margin"]
    account["total_pnl_pln"] = round(account["total_pnl_pln"] + pnl_pln, 2)
    account["total_pnl_usd"] = round(account["total_pnl_usd"] + pnl_usd, 2)
    account["closed_trades"] += 1

    if pnl_usd >= 0:
        account["win_count"] += 1
    else:
        account["loss_count"] += 1

    total_closed = account["win_count"] + account["loss_count"]
    account["win_rate"] = round((account["win_count"] / total_closed * 100) if total_closed > 0 else 0, 1)

    # Move to closed positions
    closed_pos = {
        **position,
        "exit_price": exit_price,
        "pnl_usd": round(pnl_usd, 2),
        "pnl_pln": round(pnl_pln, 2),
        "closed_at": datetime.utcnow().isoformat(),
        "status": "closed",
        "result": "win" if pnl_usd >= 0 else "loss"
    }
    closed_positions.insert(0, closed_pos)
    open_positions.pop(pos_index)

    account["open_trades"] = len(open_positions)
    account["positions"] = len(open_positions)

    # Persist to MongoDB
    db.save_trade(closed_pos)
    db.save_account(account)

    result_emoji = "+" if pnl_usd >= 0 else ""
    log_event(
        f"[TRADE] Closed {position['direction'].upper()} {position['symbol']} @ {exit_price:.2f} | P&L: {result_emoji}{pnl_pln:.2f} PLN ({result_emoji}{pnl_usd:.2f} USD)",
        "success" if pnl_usd >= 0 else "warning"
    )

    update_account_equity()
    return {"status": "closed", "position": closed_pos}

@app.get("/api/trades/open")
async def get_open_trades():
    """Get all open positions with live P&L"""
    update_account_equity()
    return {"positions": open_positions, "count": len(open_positions)}

@app.get("/api/trades/history")
async def get_trade_history(limit: int = Query(50, ge=1, le=200)):
    """Get closed trade history"""
    return {
        "trades": closed_positions[:limit],
        "total": len(closed_positions),
        "win_count": account["win_count"],
        "loss_count": account["loss_count"],
        "win_rate": account["win_rate"],
        "total_pnl_pln": account["total_pnl_pln"],
        "total_pnl_usd": account["total_pnl_usd"]
    }

@app.post("/api/account/reset")
async def reset_account():
    """Reset simulated account to starting balance"""
    global account, open_positions, closed_positions
    open_positions = []
    closed_positions = []
    account.update({
        "balance_pln": 10000.0,
        "equity_pln": 10000.0,
        "balance_usd": 2469.14,
        "equity_usd": 2469.14,
        "positions": 0,
        "open_trades": 0,
        "closed_trades": 0,
        "total_pnl_pln": 0.0,
        "total_pnl_usd": 0.0,
        "win_count": 0,
        "loss_count": 0,
        "win_rate": 0.0,
        "used_margin": 0.0,
        "available_pln": 10000.0,
    })
    # Clear DB
    db.delete_all_trades()
    db.save_account(account)
    log_event("[ACCOUNT] Reset to 10,000.00 PLN", "event")
    return {"status": "reset", "account": account}

# =====================
# NEWS & CHART ENDPOINTS
# =====================

@app.get("/api/news/all")
async def get_all_news():
    """Get latest news for all symbols"""
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
            if i < len(INSTRUMENTS) - 1:
                await asyncio.sleep(0.5)
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
async def get_chart_data(symbol: str, resolution: str = "60", count: int = 50):
    """Get historical chart data for a symbol"""
    global alpha_client
    if alpha_client is None:
        alpha_client = get_alpha_vantage_client()

    try:
        candles = alpha_client.get_candles(symbol, resolution, count)

        if candles and len(candles) > 0:
            chart_data = []
            for candle in candles:
                timestamp = candle["timestamp"]
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    if resolution in ['1', '5', '15']:
                        time_str = dt.strftime('%H:%M')
                    elif resolution in ['30', '60']:
                        time_str = dt.strftime('%H:00')
                    elif resolution == 'D':
                        time_str = dt.strftime('%m/%d')
                    else:
                        time_str = dt.strftime('%H:%M')
                except Exception:
                    time_str = timestamp[:5] if len(timestamp) >= 5 else timestamp

                chart_data.append({
                    "time": time_str,
                    "close": round(candle["close"], 2),
                    "open": round(candle["open"], 2),
                    "high": round(candle["high"], 2),
                    "low": round(candle["low"], 2),
                    "volume": candle["volume"]
                })

            return {"symbol": symbol, "data": chart_data, "resolution": resolution, "count": len(chart_data), "source": "alpha_vantage"}
        else:
            price_feeder = get_realistic_price_feeder()
            candles = price_feeder.get_candles(symbol, resolution, count)

            if candles:
                chart_data = [{
                    "time": c["time"],
                    "close": round(c["close"], 2),
                    "open": round(c["open"], 2),
                    "high": round(c["high"], 2),
                    "low": round(c["low"], 2),
                    "volume": c["volume"]
                } for c in candles]

                return {"symbol": symbol, "data": chart_data, "resolution": resolution, "count": len(chart_data), "source": "realistic_feeder"}
            else:
                return {"error": f"No chart data available for {symbol}"}

    except Exception as e:
        log_event(f"Error fetching chart data for {symbol}: {e}", "error")
        return {"error": f"Failed to fetch chart data for {symbol}"}

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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
