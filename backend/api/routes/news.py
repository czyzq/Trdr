"""News API routes - extracted from main.py"""
from datetime import datetime
from fastapi import APIRouter
import asyncio
from services.state import get_instruments
from app.logging import log_event
from alpha_vantage_news import get_client as get_news_client

router = APIRouter(tags=["news"])


@router.get("/api/news/all")
async def get_all_news():
    """Get latest news for all symbols."""
    log_event("Fetching news for all symbols...", "info")
    news_client = get_news_client()
    instruments = get_instruments()
    all_news = []

    for i, (symbol, info) in enumerate(instruments.items()):
        try:
            news = await news_client.get_news(symbol, limit=5)
            if news:
                for article in news:
                    article["symbol"] = symbol
                    article["name"] = info.get("name", symbol)
                all_news.extend(news)
            if i < len(instruments) - 1:
                await asyncio.sleep(12)
        except Exception as e:
            log_event(f"Failed to scrape news for {symbol}: {e}", "error")

    all_news.sort(key=lambda x: x.get("importance", 0), reverse=True)
    return {"news": all_news, "timestamp": datetime.utcnow().isoformat()}


@router.get("/api/news/{symbol}")
async def get_news(symbol: str):
    news_client = get_news_client()
    try:
        news = await news_client.get_news(symbol, limit=5)
        return {"symbol": symbol, "news": news or [], "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"symbol": symbol, "news": [], "timestamp": datetime.utcnow().isoformat()}
