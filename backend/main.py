"""
CFD Trading Bot - FastAPI Backend
Real-time signal generation using Finnhub data and technical indicators
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import uvicorn
import asyncio
from typing import List, Optional
import os
import json
from dotenv import load_dotenv

from models import Signal, SignalDirection, Component, ComponentType, SignalResponse
from alpha_vantage import get_client as get_alpha_vantage_client
from alpha_vantage_news import get_client as get_news_client
from realistic_prices import get_feeder as get_realistic_price_feeder
from indicators import TechnicalIndicators
from imessage_alerts import AlertConfig, iMessageAlertDispatcher, get_dispatcher
from openclaw_integration import set_openclaw_message_function, format_imessage_for_cfd_alert

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

# Signal history cache for trend analysis
signal_history_cache = {}  # {symbol: [previous_scores...]}

def load_signal_cache():
    """Load signal history cache from file"""
    global signal_history_cache
    try:
        cache_file = "signal_cache.json"
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                signal_history_cache = json.load(f)
            log_event(f"Loaded signal history cache with {len(signal_history_cache)} symbols")
    except Exception as e:
        log_event(f"Failed to load signal cache: {e}", "warning")
        signal_history_cache = {}

def save_signal_cache():
    """Save signal history cache to file"""
    try:
        cache_file = "signal_cache.json"
        with open(cache_file, 'w') as f:
            json.dump(signal_history_cache, f)
        log_event(f"Saved signal history cache with {len(signal_history_cache)} symbols")
    except Exception as e:
        log_event(f"Failed to save signal cache: {e}", "error")

# Instruments to monitor
INSTRUMENTS = {
    "XAU": {"name": "Gold", "multiplier": 1},
    "XAG": {"name": "Silver", "multiplier": 1},
    "US100": {"name": "Nasdaq-100", "multiplier": 1}
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

def calculate_trend_score(current_score: float, previous_scores: List[float]) -> float:
    """
    Calculate trend-based score adjustment based on previous signal scores
    """
    if not previous_scores or len(previous_scores) < 2:
        return 0.0
    
    # Calculate trend (moving average of recent changes)
    recent_scores = previous_scores[-5:]  # Last 5 scores
    if len(recent_scores) < 2:
        return 0.0
    
    # Calculate momentum (rate of change)
    score_changes = [recent_scores[i] - recent_scores[i-1] for i in range(1, len(recent_scores))]
    avg_change = sum(score_changes) / len(score_changes)
    
    # Calculate consistency (how consistently the trend is moving in one direction)
    positive_changes = sum(1 for change in score_changes if change > 0)
    negative_changes = sum(1 for change in score_changes if change < 0)
    consistency = abs(positive_changes - negative_changes) / len(score_changes)
    
    # Trend bonus: strengthen signals that are consistent with recent trend
    trend_bonus = avg_change * consistency * 0.2  # 20% max adjustment
    
    # Mean reversion penalty: reduce signals that are far from recent average
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
            
            # Fetch news and calculate sentiment (async web scraping)
            news_score = 0.0
            try:
                # Use async web scraping - only real data, no mocks
                news = await news_client_instance.get_news(symbol, limit=5)
                if news and len(news) > 0:
                    # Average sentiment across all news articles
                    sentiments = [article.get('sentiment', 0) for article in news]
                    news_score = sum(sentiments) / len(sentiments) if sentiments else 0
                    log_event(f"News sentiment for {symbol}: {news_score:.2f} ({len(news)} articles)", "info")
                else:
                    log_event(f"No news available for {symbol}", "info")
                    news_score = 0.0  # Neutral when no news
            except Exception as e:
                log_event(f"Failed to fetch news for {symbol}: {e}", "warning")
                news_score = 0.0  # Neutral when news fails
            
            # Generate signal with news sentiment
            technical_score, components = calculate_signal_score(indicators)
            
            # Get previous scores for trend analysis
            previous_scores = signal_history_cache.get(symbol, [])
            
            # Calculate trend-based score adjustment
            trend_adjustment = calculate_trend_score(technical_score, previous_scores)
            
            # Apply trend adjustment to technical score
            adjusted_technical_score = max(-1, min(1, technical_score + trend_adjustment))
            
            # Weighted composite: 40% technical (with trend), 20% price action, 40% news
            # Only include news if it's significant (|news_score| > 0.1)
            effective_news_score = news_score if abs(news_score) > 0.1 else 0.0
            
            score = (adjusted_technical_score * 0.4) + (0 * 0.2) + (effective_news_score * 0.4)
            
            direction = get_signal_direction(score)
            
            # Update signal history cache (keep last 10 scores)
            if symbol not in signal_history_cache:
                signal_history_cache[symbol] = []
            signal_history_cache[symbol].append(score)
            if len(signal_history_cache[symbol]) > 10:
                signal_history_cache[symbol].pop(0)
            
            # Save cache to file periodically (every 5 signals)
            if len(signals) % 5 == 0:
                save_signal_cache()
            
            # Calculate confidence based on score strength and component consistency
            base_confidence = min(0.95, abs(score) + 0.3)
            
            # Boost confidence if news sentiment aligns with technical analysis
            if (effective_news_score > 0 and adjusted_technical_score > 0) or (effective_news_score < 0 and adjusted_technical_score < 0):
                confidence = min(0.95, base_confidence * 1.1)  # 10% boost for aligned signals
            else:
                confidence = base_confidence
            
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
            
            # Send iMessage alert if conditions are met
            try:
                alert_dispatcher = get_dispatcher()
                alert_result = alert_dispatcher.send_alert(
                    symbol=symbol,
                    direction=direction.value,
                    score=score,
                    confidence=confidence,
                    current_price=current_price,
                    entry_point=entry_point,
                    take_profit=take_profit,
                    stop_loss=stop_loss
                )
                
                if alert_result["status"] == "sent":
                    log_event(f"[iMessage ALERT] Sent for {symbol} {direction.value}", "success")
                elif alert_result["status"] == "filtered":
                    log_event(f"[iMessage ALERT] Filtered for {symbol} (score too low)", "info")
                else:
                    log_event(f"[iMessage ALERT] Failed for {symbol}: {alert_result.get('error', 'Unknown error')}", "error")
                    
            except Exception as alert_error:
                log_event(f"[iMessage ALERT] Error sending alert for {symbol}: {str(alert_error)}", "error")
            
        except Exception as e:
            log_event(f"Error generating signal for {symbol}: {str(e)}", "error")
    
    return signals

@app.on_event("startup")
async def startup():
    """Initialize on startup"""
    log_event("[CFD TRADING BOT v0.1.0 - WEB SCRAPING EDITION]", "event")
    log_event("Initializing Alpha Vantage client...", "info")
    global alpha_client, account
    alpha_client = get_alpha_vantage_client()
    if alpha_client:
        log_event("✓ Connected to Alpha Vantage API", "success")
    else:
        log_event("✗ Failed to connect to Alpha Vantage API", "error")
    
    # Load signal history cache
    load_signal_cache()
    
    # Initialize web scraping news client
    try:
        news_client = get_news_client()
        log_event("✓ Web scraping news client initialized", "success")
    except Exception as e:
        log_event(f"✗ Failed to initialize web scraping news client: {e}", "error")
    
    # Initialize account
    account["last_scan"] = datetime.utcnow().isoformat()
    log_event(f"✓ Account initialized: Balance ${account['balance']}", "success")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    log_event("Shutting down CFD Trading Bot...", "info")
    
    # Save signal history cache
    save_signal_cache()
    
    # Close news client session
    try:
        news_client = get_news_client()
        if hasattr(news_client, 'close'):
            await news_client.close()
            log_event("✓ News client session closed", "success")
    except Exception as e:
        log_event(f"Error closing news client: {e}", "warning")
    
    log_event("✓ Shutdown complete", "success")

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
    Get latest news for all symbols (combined list) - concurrent web scraping
    """
    log_event("Fetching news for all symbols...", "info")
    news_client = get_news_client()
    
    all_news = []
    
    # Fetch news concurrently with web scraping
    for i, (symbol, info) in enumerate(INSTRUMENTS.items()):
        try:
            log_event(f"Scraping news for {symbol} ({info['name']})...")
            news = await news_client.get_news(symbol, limit=5)
            if news:
                # Add symbol + name to each article
                for article in news:
                    article["symbol"] = symbol
                    article["name"] = info["name"]
                all_news.extend(news)
                log_event(f"Scraped {len(news)} articles for {symbol}")
            else:
                log_event(f"No news scraped for {symbol}", "info")
                # No mock news fallback - only real data
            
            # Small delay between requests to be respectful to websites
            if i < len(INSTRUMENTS) - 1:
                await asyncio.sleep(0.5)  # 500ms delay
                
        except Exception as e:
            log_event(f"Failed to scrape news for {symbol}: {e}", "error")
            # No mock news fallback - only real data
    
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
    Get latest news and sentiment for a symbol (web scraping)
    """
    log_event(f"Scraping news for {symbol}...", "info")
    news_client = get_news_client()
    
    try:
        news = await news_client.get_news(symbol, limit=5)
        if not news:
            log_event(f"No news scraped for {symbol}", "info")
            news = []  # Empty list when no real news available
        else:
            log_event(f"Scraped {len(news)} articles for {symbol}", "success")
        
        return {
            "symbol": symbol,
            "news": news if news else [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        log_event(f"Failed to scrape news for {symbol}: {e}", "error")
        # Return empty news list on complete failure
        return {
            "symbol": symbol,
            "news": [],
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

@app.get("/api/chart/{symbol}")
async def get_chart_data(symbol: str, resolution: str = "60", count: int = 50):
    """
    Get historical chart data for a symbol
    resolution: 1, 5, 15, 30, 60 (minutes) or D (daily)
    count: number of data points to return
    """
    global alpha_client
    if alpha_client is None:
        alpha_client = get_alpha_vantage_client()
    
    log_event(f"Fetching chart data for {symbol} (resolution: {resolution}, count: {count})")
    print(f"[DEBUG] Chart endpoint called with symbol={symbol}")
    
    try:
        # Try Alpha Vantage first for real data
        candles = alpha_client.get_candles(symbol, resolution, count)
        
        if candles and len(candles) > 0:
            log_event(f"Retrieved {len(candles)} candles from Alpha Vantage for {symbol}")
            
            # Format for frontend chart with proper timestamp formatting
            chart_data = []
            for i, candle in enumerate(candles):
                # Format timestamp based on resolution for consistent X-axis labels
                timestamp = candle["timestamp"]
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    if resolution in ['1', '5', '15']:
                        # For intraday: show HH:MM
                        time_str = dt.strftime('%H:%M')
                    elif resolution in ['30', '60']:
                        # For hourly: show HH:00
                        time_str = dt.strftime('%H:00')
                    elif resolution == 'D':
                        # For daily: show MM/DD
                        time_str = dt.strftime('%m/%d')
                    else:
                        # Default fallback
                        time_str = dt.strftime('%H:%M')
                except:
                    # Fallback to original timestamp if parsing fails
                    time_str = timestamp[:5] if len(timestamp) >= 5 else timestamp
                
                chart_data.append({
                    "time": time_str,
                    "close": round(candle["close"], 2),
                    "open": round(candle["open"], 2),
                    "high": round(candle["high"], 2),
                    "low": round(candle["low"], 2),
                    "volume": candle["volume"]
                })
            
            return {
                "symbol": symbol,
                "data": chart_data,
                "resolution": resolution,
                "count": len(chart_data),
                "source": "alpha_vantage"
            }
        else:
            # Fallback to realistic price feeder
            log_event(f"Alpha Vantage data unavailable, using realistic feeder for {symbol}")
            price_feeder = get_realistic_price_feeder()
            candles = price_feeder.get_candles(symbol, resolution, count)
            
            if candles:
                chart_data = []
                for i, candle in enumerate(candles):
                    # Use the already formatted time from realistic feeder
                    chart_data.append({
                        "time": candle["time"],  # Already formatted by realistic feeder
                        "close": round(candle["close"], 2),
                        "open": round(candle["open"], 2),
                        "high": round(candle["high"], 2),
                        "low": round(candle["low"], 2),
                        "volume": candle["volume"]
                    })
                
                return {
                    "symbol": symbol,
                    "data": chart_data,
                    "resolution": resolution,
                    "count": len(chart_data),
                    "source": "realistic_feeder"
                }
            else:
                return {"error": f"No chart data available for {symbol}"}
                
    except Exception as e:
        log_event(f"Error fetching chart data for {symbol}: {e}", "error")
        return {"error": f"Failed to fetch chart data for {symbol}"}

# iMessage Alert Endpoints
@app.get("/api/alerts/config")
async def get_alert_config():
    """Get current iMessage alert configuration"""
    dispatcher = get_dispatcher()
    return dispatcher.config.dict()

@app.post("/api/alerts/config")
async def update_alert_config(config: AlertConfig):
    """Update iMessage alert configuration"""
    dispatcher = get_dispatcher()
    dispatcher.update_config(config)
    log_event(f"Alert config updated: enabled={config.enabled}, recipient={config.recipient_phone}", "info")
    return {"status": "updated", "config": dispatcher.config.dict()}

@app.post("/api/alerts/test")
async def send_test_alert():
    """Send a test iMessage alert"""
    dispatcher = get_dispatcher()
    
    if not dispatcher.config.enabled:
        return {"status": "error", "message": "Alerts are disabled. Enable them first."}
    
    try:
        result = dispatcher.send_alert(
            symbol="TEST",
            direction="buy",
            score=0.8,
            confidence=0.85,
            current_price=50000.0,
            entry_point=49500.0,
            take_profit=51000.0,
            stop_loss=49000.0
        )
        
        if result["status"] == "sent":
            log_event("Test iMessage alert sent successfully", "success")
            return {"status": "sent", "message_id": result.get("message_id")}
        else:
            return {"status": "error", "message": result.get("error", "Failed to send test alert")}
            
    except Exception as e:
        log_event(f"Error sending test alert: {e}", "error")
        return {"status": "error", "message": str(e)}

@app.get("/api/alerts/history")
async def get_alert_history(
    symbol: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
):
    """Get iMessage alert history"""
    dispatcher = get_dispatcher()
    history = dispatcher.get_alert_history(symbol=symbol, limit=limit)
    return {
        "history": history,
        "total": len(history),
        "symbol_filter": symbol
    }

@app.delete("/api/alerts/history")
async def clear_alert_history():
    """Clear iMessage alert history"""
    dispatcher = get_dispatcher()
    dispatcher.clear_history()
    log_event("Alert history cleared", "info")
    return {"status": "cleared"}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    
    log_event(f"Starting CFD Trading Bot API server on {args.host}:{args.port}...", "info")
    uvicorn.run(app, host=args.host, port=args.port)
