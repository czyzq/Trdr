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
from indicators import TechnicalIndicators
from imessage_alerts import AlertConfig, iMessageAlertDispatcher, get_dispatcher
from openclaw_integration import set_openclaw_message_function, format_imessage_for_cfd_alert
import database as db
from broker_factory import create_broker, create_data_provider

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

async def generate_signals() -> List[Signal]:
    """Generate trading signals for all instruments using regime-adaptive scoring"""
    global alpha_client, account

    account["last_scan"] = datetime.utcnow().isoformat()

    # Track peak balance for drawdown calculation
    if account["balance_pln"] > account.get("peak_balance_pln", INITIAL_BALANCE_PLN):
        account["peak_balance_pln"] = account["balance_pln"]

    news_client_instance = get_news_client()

    signals = []

    for symbol, info in INSTRUMENTS.items():
        try:
            log_event(f"Analyzing {symbol} ({info['name']})...")

            quote = data_provider.get_quote(symbol)
            if not quote:
                log_event(f"Failed to generate price for {symbol}", "error")
                continue

            current_price = quote["price"]

            candles = data_provider.get_candles(symbol, resolution="60", count=100)
            if not candles or len(candles) < 50:
                log_event(f"Insufficient candle data for {symbol} ({len(candles) if candles else 0} bars)", "error")
                continue

            indicators = TechnicalIndicators.calculate_all(candles, period=14)
            if not indicators:
                log_event(f"Failed to calculate indicators for {symbol}", "warning")
                continue

            indicators["_closes"] = [c["close"] for c in candles]

            # ── Volatility filter ──
            atr = indicators.get("atr_14", current_price * 0.01)
            atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
            # Skip if volatility is extreme (>3% per candle = dangerous)
            if atr_pct > 3.0:
                log_event(f"[SKIP] {symbol} ATR {atr_pct:.1f}% too volatile", "warning")
                continue

            # ── Technical scoring (regime-adaptive) ──
            technical_score, components = calculate_signal_score(indicators, symbol)

            # ── News sentiment (capped influence: max 15% of final score) ──
            news_score = 0.0
            try:
                news = await news_client_instance.get_news(symbol, limit=5)
                if news and len(news) > 0:
                    sentiments = [article.get('sentiment', 0) for article in news]
                    news_score = sum(sentiments) / len(sentiments) if sentiments else 0
                    log_event(f"News sentiment for {symbol}: {news_score:.2f} ({len(news)} articles)")
            except Exception as e:
                log_event(f"Failed to fetch news for {symbol}: {e}", "warning")

            # Final score: 85% technical + 15% news (only if news is available and meaningful)
            effective_news = news_score if abs(news_score) > 0.1 else 0.0
            if effective_news != 0:
                score = technical_score * 0.85 + effective_news * 0.15
            else:
                score = technical_score  # 100% technical when no news
            score = max(-1, min(1, score))

            # ── Per-instrument entry threshold ──
            min_score = info.get("min_score", 0.15)
            direction = get_signal_direction(score, min_score=min_score)

            # ── Minimum indicator agreement filter (per-instrument) ──
            component_vals = [c.value for c in components]
            bullish_c = sum(1 for v in component_vals if v > 0.1)
            bearish_c = sum(1 for v in component_vals if v < -0.1)
            # Commodities need more agreement (3), equities/crypto need less (2)
            min_agreement = 3 if info.get("asset_class") == "commodity" else 2
            if direction != SignalDirection.NEUTRAL and max(bullish_c, bearish_c) < min_agreement:
                log_event(f"[SKIP] {symbol} only {max(bullish_c, bearish_c)} indicators agree (need {min_agreement})", "info")
                direction = SignalDirection.NEUTRAL

            # ── Trend-alignment filter for commodities ──
            # Commodities (gold, silver) mean-revert — only trade with the larger trend
            sma_50 = indicators.get("sma_50")
            if info.get("asset_class") == "commodity" and sma_50 and direction != SignalDirection.NEUTRAL:
                price_above_sma50 = current_price > sma_50
                is_buy = direction in (SignalDirection.BUY, SignalDirection.STRONG_BUY)
                # Only allow buys when price is above SMA50 (uptrend), sells when below
                if is_buy and not price_above_sma50:
                    log_event(f"[SKIP] {symbol} BUY rejected: price below SMA50 (counter-trend)", "info")
                    direction = SignalDirection.NEUTRAL
                elif not is_buy and price_above_sma50:
                    log_event(f"[SKIP] {symbol} SELL rejected: price above SMA50 (counter-trend)", "info")
                    direction = SignalDirection.NEUTRAL

            # ── Signal history tracking ──
            if symbol not in signal_history_cache:
                signal_history_cache[symbol] = []
            signal_history_cache[symbol].append(score)
            if len(signal_history_cache[symbol]) > 20:
                signal_history_cache[symbol].pop(0)
            if len(signals) % 4 == 0:
                save_signal_cache()

            # ── Confidence based on component agreement ──
            component_values = [c.value for c in components]
            if component_values:
                bullish_count = sum(1 for v in component_values if v > 0.1)
                bearish_count = sum(1 for v in component_values if v < -0.1)
                total_opinionated = bullish_count + bearish_count
                agreement = max(bullish_count, bearish_count) / max(total_opinionated, 1)
                confidence = min(0.95, abs(score) * agreement + 0.1)
            else:
                confidence = 0.1

            # ── TP/SL with ATR-based adaptive levels ──
            # With trailing stop enabled: wider initial SL (3×ATR emergency)
            # The trailing mechanism will tighten the SL once in profit
            entry_point = current_price
            adx_data = indicators.get("adx")
            is_trending = adx_data and adx_data["adx"] > 25
            use_trailing = info.get("trailing_stop", False)

            if use_trailing:
                # Wide emergency SL — trailing stop manages the real exit
                sl_mult = 3.0
                tp_mult = 4.0 if is_trending else 3.5
            else:
                if is_trending:
                    sl_mult, tp_mult = 1.5, 3.5
                else:
                    sl_mult, tp_mult = 1.5, 3.0

            if direction in [SignalDirection.BUY, SignalDirection.STRONG_BUY]:
                stop_loss = entry_point - (atr * sl_mult)
                take_profit = entry_point + (atr * tp_mult)
            else:
                stop_loss = entry_point + (atr * sl_mult)
                take_profit = entry_point - (atr * tp_mult)

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
    """Get historical chart data for a symbol. Returns real data only (never synthetic)."""
    global alpha_client
    if alpha_client is None:
        alpha_client = get_alpha_vantage_client()

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
                "close": round(candle["close"], 2),
                "open": round(candle["open"], 2),
                "high": round(candle["high"], 2),
                "low": round(candle["low"], 2),
                "volume": candle.get("volume", 0)
            })
        return chart_data

    # Try live Alpha Vantage data
    try:
        candles = alpha_client.get_candles(symbol, resolution, count)
        if candles and len(candles) > 0:
            chart_data = _format_candles(candles)
            fetched_at = datetime.utcnow().isoformat()
            # Cache to DB for future fallback
            db.save_candles(symbol, resolution, chart_data, "alpha_vantage")
            return {
                "symbol": symbol, "data": chart_data, "resolution": resolution,
                "count": len(chart_data), "source": "alpha_vantage",
                "fetched_at": fetched_at,
            }
    except Exception as e:
        log_event(f"Alpha Vantage chart fetch failed for {symbol}: {e}", "warning")

    # Fallback: load last cached real data from DB
    cached = db.load_candles(symbol, resolution)
    if cached and cached.get("candles"):
        return {
            "symbol": symbol, "data": cached["candles"], "resolution": resolution,
            "count": len(cached["candles"]), "source": "cache",
            "fetched_at": cached["fetched_at"],
        }

    return {"error": f"No real data available for {symbol}. Check API key or try again later."}

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
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
