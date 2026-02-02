"""
News client with Brave Search integration and sentiment analysis
Respects API rate limits (1 req/sec)
"""
import os
import time
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
BRAVE_BASE_URL = "https://api.search.brave.com/res/v1/web/search"

BULLISH_KEYWORDS = [
    "beat", "rally", "surge", "approval", "upgrade", "bullish", 
    "gain", "rise", "jump", "outperform", "positive", "record",
    "strong", "profit", "growth", "win", "success", "boost"
]

BEARISH_KEYWORDS = [
    "miss", "crash", "down", "reject", "downgrade", "bearish",
    "loss", "fall", "drop", "underperform", "negative", "decline",
    "weak", "loss", "shrink", "fail", "concern", "risk"
]

class NewsClient:
    def __init__(self, api_key: str = BRAVE_API_KEY):
        self.api_key = api_key
        self.base_url = BRAVE_BASE_URL
        self.client = httpx.Client()
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = 120  # Cache for 2 minutes
        self.last_api_call = 0
        self.min_interval = 1.0  # 1 second between requests
    
    def _rate_limit(self):
        """Respect API rate limits (1 req/sec)"""
        elapsed = time.time() - self.last_api_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_api_call = time.time()
    
    def _calculate_sentiment(self, headline: str) -> tuple[float, str]:
        """
        Calculate sentiment from headline text
        Returns: (score: -1 to +1, direction: 'buy'/'sell'/'neutral')
        """
        headline_lower = headline.lower()
        
        bullish = sum(1 for word in BULLISH_KEYWORDS if word in headline_lower)
        bearish = sum(1 for word in BEARISH_KEYWORDS if word in headline_lower)
        
        total = bullish + bearish
        if total == 0:
            return 0.0, "neutral"
        
        # Sentiment score: -1 (bearish) to +1 (bullish)
        sentiment = (bullish - bearish) / total if total > 0 else 0
        
        if sentiment > 0.2:
            direction = "buy"
        elif sentiment < -0.2:
            direction = "sell"
        else:
            direction = "neutral"
        
        return sentiment, direction
    
    def get_news(self, symbol: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch news for a symbol from Brave Search
        """
        # Check cache first
        if symbol in self.cache:
            if time.time() - self.cache_time.get(symbol, 0) < self.cache_ttl:
                return self.cache[symbol]
        
        try:
            self._rate_limit()
            
            # Map futures symbols to searchable terms
            symbol_map = {
                "GC=F": "gold price news",
                "SI=F": "silver price news",
                "NQ=F": "nasdaq nasdaq-100 news"
            }
            
            query = symbol_map.get(symbol, symbol)
            
            params = {
                "q": query,
                "count": limit,
                "freshness": "past-24h"  # Only recent news
            }
            
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key
            }
            
            response = self.client.get(
                self.base_url, 
                params=params, 
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            news = []
            if "web" in data:
                for article in data["web"][:limit]:
                    headline = article.get("title", "")
                    
                    # Skip if no headline
                    if not headline:
                        continue
                    
                    sentiment, direction = self._calculate_sentiment(headline)
                    
                    # Calculate importance (0-1)
                    # Based on: recency + length of title + keyword match
                    published = article.get("published", "")
                    title_length = len(headline)
                    keyword_match = min(1.0, (abs(sentiment) * 0.5) + 0.5)
                    
                    # Recency: newer = higher importance
                    importance = keyword_match * 0.7 + 0.3  # Base importance
                    
                    news.append({
                        "headline": headline[:100],  # Limit to 100 chars
                        "sentiment": sentiment,
                        "direction": direction,
                        "importance": min(1.0, importance),
                        "source": article.get("source", "Unknown"),
                        "url": article.get("url", ""),
                        "published": published
                    })
            
            # Cache it
            self.cache[symbol] = news
            self.cache_time[symbol] = time.time()
            
            return news if news else None
            
        except Exception as e:
            print(f"Error fetching news for {symbol}: {e}")
            return None
    
    def close(self):
        """Close HTTP client"""
        self.client.close()

# Singleton
_client = None

def get_client() -> NewsClient:
    global _client
    if _client is None:
        _client = NewsClient()
    return _client
