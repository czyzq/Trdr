"""
CFD Trading Bot - FastAPI Backend
Real-time signal generation using Finnhub data and technical indicators
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import uvicorn
import asyncio
from typing import List, Optional
import os
from dotenv import load_dotenv

from models import Signal, SignalDirection, Component, ComponentType, SignalResponse
from alpha_vantage import get_client as get_alpha_vantage_client
from news_client import get_client as get_news_client
from realistic_prices import get_feeder as get_realistic_price_feeder
from indicators import TechnicalIndicators

load_dotenv()

app = FastAPI(
    title="CFD Trading Bot API",
    description="Real-time trading signals for CFD instruments (Gold, Silver, Nasdaq)",
    version="0.1.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
signals_cache = {}
alpha_client = None
event_log = []
account = {
    "balance": 1000.0,
    "equity": 1000.0,
    "positions": 0,
    "used_margin": 0.0,
    "available": 1000.0,
    "last_scan": datetime.utcnow().isoformat(),
    "dry_run": True,  # Simulation mode - no real trades
    "mode": "simulate"  # "simulate" or "live"
}

# Instruments to monitor
INSTRUMENTS = {
    "GC=F": {"name": "Gold", "multiplier": 1},
    "SI=F": {"name": "Silver", "multiplier": 1},
    "NQ=F": {"name": "Nasdaq-100", "multiplier": 1}
}

def log_event(message: str, log_type: str = "info"):
    """Log events for the console"""
    event_log.append({
        "id": str(len(event_log)),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "message": message,
        "type": log_type
    })
    # Keep only last 100 events
    if len(event_log) > 100:
        event_log.pop(0)
    print(f"[{log_type.upper()}] {message}")

def calculate_signal_score(indicators: dict) -> tuple[float, List[Component]]:
    """
    Calculate composite signal score from indicators
    Returns score (-1 to +1) and components breakdown
    """
    components = []
    scores = []
    weights = []
    
    # RSI component (0-100, normalize to -1 to +1)
    if indicators.get("rsi_14"):
        rsi = indicators["rsi_14"]
        # RSI: <30 = oversold (bearish), >70 = overbought (bullish)
        rsi_score = (rsi - 50) / 50  # normalize to -1 to +1
        components.append(Component(
            type=ComponentType.TECHNICAL,
            name="RSI (14)",
            value=rsi_score,
            description=f"RSI at {rsi:.1f}",
            confidence=0.8,
            indicators={"value": rsi}
        ))
        scores.append(rsi_score)
        weights.append(0.35)
    
    # MACD component
    if indicators.get("macd"):
        macd = indicators["macd"]
        if macd.get("histogram") is not None:
            # Positive histogram = bullish, negative = bearish
            histogram = macd["histogram"]
            # Normalize to -1 to +1
            macd_score = max(-1, min(1, histogram / 100)) if histogram != 0 else 0
            components.append(Component(
                type=ComponentType.TECHNICAL,
                name="MACD",
                value=macd_score,
                description=f"MACD histogram: {histogram:.4f}",
                confidence=0.75,
                indicators=macd
            ))
            scores.append(macd_score)
            weights.append(0.30)
    
    # Momentum component
    if indicators.get("momentum_10"):
        momentum = indicators["momentum_10"]
        # Normalize momentum to -1 to +1
        momentum_score = max(-1, min(1, momentum / 100)) if momentum != 0 else 0
        components.append(Component(
            type=ComponentType.TECHNICAL,
            name="Momentum (10)",
            value=momentum_score,
            description=f"Momentum: {momentum:.4f}",
            confidence=0.7,
            indicators={"value": momentum}
        ))
        scores.append(momentum_score)
        weights.append(0.35)
    
    # Calculate weighted composite score
    if scores:
        total_weight = sum(weights)
        composite_score = sum(s * w for s, w in zip(scores, weights)) / total_weight if total_weight > 0 else 0
    else:
        composite_score = 0
    
    return composite_score, components

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

async def generate_signals() -> List[Signal]:
    """
    Generate trading signals for all instruments
    """
    global alpha_client, account
    
    # Update last scan time
    account["last_scan"] = datetime.utcnow().isoformat()
    
    # Use realistic price feeder for now (Alpha Vantage doesn't support futures properly)
    price_feeder = get_realistic_price_feeder()
    news_client_instance = get_news_client()
    
    signals = []
    
    for symbol, info in INSTRUMENTS.items():
        try:
            log_event(f"Fetching data for {symbol} ({info['name']})...")
            
            # Get quote from realistic price feeder
            quote = price_feeder.get_quote(symbol)
            if not quote:
                log_event(f"Failed to generate price for {symbol}", "error")
                continue
            
            current_price = quote["price"]
            
            # Get candles (1 hour resolution, last 100 bars)
            candles = price_feeder.get_candles(symbol, resolution="60", count=100)
            if not candles or len(candles) < 26:
                log_event(f"Insufficient candle data for {symbol}", "error")
                continue
            
            # Calculate indicators
            indicators = TechnicalIndicators.calculate_all(candles, period=14)
            if not indicators:
                log_event(f"Failed to calculate indicators for {symbol}", "warning")
                continue
            
            # Fetch news and calculate sentiment
            news_score = 0.0
            try:
                news = news_client_instance.get_news(symbol, limit=5)
                if news and len(news) > 0:
                    # Average sentiment across all news articles
                    sentiments = [article.get('sentiment', 0) for article in news]
                    news_score = sum(sentiments) / len(sentiments) if sentiments else 0
                    log_event(f"News sentiment for {symbol}: {news_score:.2f} ({len(news)} articles)", "info")
            except Exception as e:
                log_event(f"Failed to fetch news for {symbol}: {e}", "warning")
            
            # Generate signal with news sentiment
            technical_score, components = calculate_signal_score(indicators)
            
            # Weighted composite: 40% technical, 20% price action, 40% news
            score = (technical_score * 0.4) + (0 * 0.2) + (news_score * 0.4)
            
            direction = get_signal_direction(score)
            
            # Calculate confidence
            confidence = min(0.95, abs(score) + 0.3)  # Score contributes to confidence
            
            # Calculate risk/reward
            rsi = indicators.get("rsi_14", 50)
            atr = indicators.get("atr_14", current_price * 0.01)  # Default to 1% of price
            
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
            log_event(f"[SIGNAL] {symbol}: {direction.value} | Score: {score:.2f} | Price: ${current_price:.2f}", "event")
            
        except Exception as e:
            log_event(f"Error generating signal for {symbol}: {str(e)}", "error")
    
    return signals

@app.on_event("startup")
async def startup():
    """Initialize on startup"""
    log_event("[CFD TRADING BOT v0.1.0]", "event")
    log_event("Initializing Alpha Vantage client...", "info")
    global alpha_client, account
    alpha_client = get_alpha_vantage_client()
    if alpha_client:
        log_event("✓ Connected to Alpha Vantage API", "success")
    else:
        log_event("✗ Failed to connect to Alpha Vantage API", "error")
    
    # Initialize account
    account["last_scan"] = datetime.utcnow().isoformat()
    log_event(f"✓ Account initialized: Balance ${account['balance']}", "success")

@app.get("/")
async def root():
    return {"message": "CFD Trading Bot API", "status": "running", "version": "0.1.0"}

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/signals", response_model=SignalResponse)
async def get_signals():
    """
    Fetch real trading signals
    """
    log_event("Generating signals on demand...", "info")
    signals = await generate_signals()
    return SignalResponse(signals=signals)

@app.get("/api/logs")
async def get_logs():
    """
    Get event logs for console
    """
    return {"logs": event_log}

@app.get("/api/account")
async def get_account():
    """
    Get account info (balance, equity, positions)
    """
    return account

@app.post("/api/account/mode")
async def set_account_mode(mode: str):
    """
    Set trading mode: "simulate" or "live"
    """
    global account
    if mode not in ["simulate", "live"]:
        return {"error": "Invalid mode. Use 'simulate' or 'live'"}
    
    account["mode"] = mode
    account["dry_run"] = (mode == "simulate")
    
    log_event(f"Trading mode changed to: {mode.upper()}", "event")
    
    return {
        "mode": account["mode"],
        "dry_run": account["dry_run"],
        "message": f"Now in {mode.upper()} mode"
    }

@app.get("/api/news/all")
async def get_all_news():
    """
    Get latest news for all symbols (combined list)
    """
    log_event("Fetching news for all symbols...", "info")
    news_client = get_news_client()
    
    all_news = []
    
    for symbol, info in INSTRUMENTS.items():
        try:
            news = news_client.get_news(symbol, limit=5)
            if news:
                # Add symbol + name to each article
                for article in news:
                    article["symbol"] = symbol
                    article["name"] = info["name"]
                all_news.extend(news)
        except Exception as e:
            log_event(f"Failed to fetch news for {symbol}: {e}", "error")
    
    # Sort by importance (highest first)
    all_news.sort(key=lambda x: x.get("importance", 0), reverse=True)
    
    log_event(f"Found {len(all_news)} total articles across all symbols", "success")
    
    return {
        "news": all_news,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/news/{symbol}")
async def get_news(symbol: str):
    """
    Get latest news and sentiment for a symbol
    """
    log_event(f"Fetching news for {symbol}...", "info")
    news_client = get_news_client()
    news = news_client.get_news(symbol, limit=5)
    if not news:
        log_event(f"No news found for {symbol}", "warning")
        return {"symbol": symbol, "news": [], "timestamp": datetime.utcnow().isoformat()}
    
    log_event(f"Found {len(news)} articles for {symbol}", "success")
    return {
        "symbol": symbol,
        "news": news,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    """
    Get current quote for a symbol
    """
    global alpha_client
    if alpha_client is None:
        alpha_client = get_alpha_vantage_client()
    
    quote = alpha_client.get_quote(symbol)
    return quote if quote else {"error": f"Failed to fetch quote for {symbol}"}

if __name__ == "__main__":
    log_event("Starting CFD Trading Bot API server...", "info")
    uvicorn.run(app, host="0.0.0.0", port=8000)
