"""
Mock news client for fallback when Brave API is unavailable
Provides realistic mock news data for testing and development
"""

import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Mock news data for different symbols
MOCK_NEWS = {
    "AAPL": [
        {
            "headline": "Apple shares rise on strong iPhone sales and services growth",
            "sentiment": 0.5,
            "direction": "buy",
            "importance": 0.8,
            "source": "Reuters",
            "url": "https://example.com/apple-iphone-sales",
            "published": (datetime.now() - timedelta(hours=1)).isoformat(),
        },
        {
            "headline": "Apple Vision Pro demand exceeds expectations in enterprise market",
            "sentiment": 0.4,
            "direction": "buy",
            "importance": 0.6,
            "source": "TechCrunch",
            "url": "https://example.com/apple-vision-pro-enterprise",
            "published": (datetime.now() - timedelta(hours=3)).isoformat(),
        },
        {
            "headline": "Apple faces supply chain challenges in China manufacturing",
            "sentiment": -0.3,
            "direction": "sell",
            "importance": 0.5,
            "source": "Wall Street Journal",
            "url": "https://example.com/apple-supply-chain",
            "published": (datetime.now() - timedelta(hours=5)).isoformat(),
        },
    ],
    "TSLA": [
        {
            "headline": "Tesla delivers record number of vehicles in latest quarter",
            "sentiment": 0.7,
            "direction": "buy",
            "importance": 0.9,
            "source": "Bloomberg",
            "url": "https://example.com/tesla-deliveries",
            "published": (datetime.now() - timedelta(hours=2)).isoformat(),
        },
        {
            "headline": "Tesla Cybertruck production ramps up ahead of schedule",
            "sentiment": 0.6,
            "direction": "buy",
            "importance": 0.7,
            "source": "CNBC",
            "url": "https://example.com/tesla-cybertruck",
            "published": (datetime.now() - timedelta(hours=4)).isoformat(),
        },
        {
            "headline": "Tesla faces increased competition in EV market from traditional automakers",
            "sentiment": -0.2,
            "direction": "sell",
            "importance": 0.4,
            "source": "MarketWatch",
            "url": "https://example.com/tesla-competition",
            "published": (datetime.now() - timedelta(hours=6)).isoformat(),
        },
    ],
    "GC=F": [
        {
            "headline": "Gold prices edge higher as dollar weakens ahead of Fed meeting",
            "sentiment": 0.3,
            "direction": "buy",
            "importance": 0.8,
            "source": "Reuters",
            "url": "https://example.com/gold-fed-meeting",
            "published": (datetime.now() - timedelta(hours=1)).isoformat(),
        },
        {
            "headline": "Gold demand rises in India as wedding season approaches",
            "sentiment": 0.5,
            "direction": "buy",
            "importance": 0.6,
            "source": "Bloomberg",
            "url": "https://example.com/gold-india-demand",
            "published": (datetime.now() - timedelta(hours=3)).isoformat(),
        },
        {
            "headline": "Central banks continue gold buying spree amid economic uncertainty",
            "sentiment": 0.7,
            "direction": "buy",
            "importance": 0.9,
            "source": "Financial Times",
            "url": "https://example.com/central-banks-gold",
            "published": (datetime.now() - timedelta(hours=5)).isoformat(),
        },
    ],
    "SI=F": [
        {
            "headline": "Silver surges on industrial demand and solar panel growth",
            "sentiment": 0.6,
            "direction": "buy",
            "importance": 0.7,
            "source": "MarketWatch",
            "url": "https://example.com/silver-solar-demand",
            "published": (datetime.now() - timedelta(hours=2)).isoformat(),
        },
        {
            "headline": "Silver ETF inflows hit monthly high as investors seek alternatives",
            "sentiment": 0.4,
            "direction": "buy",
            "importance": 0.5,
            "source": "CNBC",
            "url": "https://example.com/silver-etf-inflows",
            "published": (datetime.now() - timedelta(hours=4)).isoformat(),
        },
    ],
    "NQ=F": [
        {
            "headline": "Nasdaq futures rise as tech earnings beat expectations",
            "sentiment": 0.4,
            "direction": "buy",
            "importance": 0.8,
            "source": "Yahoo Finance",
            "url": "https://example.com/nasdaq-tech-earnings",
            "published": (datetime.now() - timedelta(hours=1)).isoformat(),
        },
        {
            "headline": "AI stocks lead Nasdaq higher amid breakthrough announcements",
            "sentiment": 0.6,
            "direction": "buy",
            "importance": 0.7,
            "source": "TechCrunch",
            "url": "https://example.com/nasdaq-ai-stocks",
            "published": (datetime.now() - timedelta(hours=6)).isoformat(),
        },
        {
            "headline": "Nasdaq volatility expected ahead of major tech IPO",
            "sentiment": -0.2,
            "direction": "sell",
            "importance": 0.4,
            "source": "Wall Street Journal",
            "url": "https://example.com/nasdaq-volatility-ipo",
            "published": (datetime.now() - timedelta(hours=8)).isoformat(),
        },
    ],
}


def get_mock_news(symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get mock news for a symbol
    """
    if symbol not in MOCK_NEWS:
        return []

    news = MOCK_NEWS[symbol].copy()

    # Add some randomness to make it feel more realistic
    for article in news:
        # Randomly adjust sentiment slightly
        original_sentiment = article["sentiment"]
        article["sentiment"] = original_sentiment + random.uniform(-0.1, 0.1)
        article["sentiment"] = max(-1, min(1, article["sentiment"]))

        # Update direction based on new sentiment
        if article["sentiment"] > 0.2:
            article["direction"] = "buy"
        elif article["sentiment"] < -0.2:
            article["direction"] = "sell"
        else:
            article["direction"] = "neutral"

        # Randomly adjust importance
        article["importance"] = max(0, min(1, article["importance"] + random.uniform(-0.1, 0.1)))

    # Sort by importance (highest first) and return limited results
    news.sort(key=lambda x: x["importance"], reverse=True)
    return news[:limit]
