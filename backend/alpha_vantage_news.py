"""
Alpha Vantage News and Insider Transactions Client
More reliable than Brave API with better rate limits
"""
import os
import time
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
from mock_news import get_mock_news

load_dotenv()

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
ALPHA_BASE_URL = "https://www.alphavantage.co/query"

class AlphaVantageClient:
    def __init__(self, api_key: str = ALPHA_VANTAGE_API_KEY):
        self.api_key = api_key
        self.base_url = ALPHA_BASE_URL
        self.client = httpx.Client()
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = 300  # Cache for 5 minutes
        self.last_api_call = 0
        self.min_interval = 12.0  # Alpha Vantage: 5 calls per minute = 12 seconds between calls
        
    def _rate_limit(self):
        """Respect Alpha Vantage rate limits (5 calls per minute)"""
        elapsed = time.time() - self.last_api_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_api_call = time.time()
    
    def get_news_sentiment(self, symbol: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
        """
        Get news sentiment for a symbol using Alpha Vantage NEWS_SENTIMENT API
        Returns real news data or empty list if unavailable (no mock data)
        """
        # Check cache first
        cache_key = f"news_{symbol}"
        if cache_key in self.cache:
            if time.time() - self.cache_time.get(cache_key, 0) < self.cache_ttl:
                print(f"Using cached news for {symbol}")
                return self.cache[cache_key]
        
        # Try real Alpha Vantage API (no mock data fallback)
        try:
            self._rate_limit()
            
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": symbol,
                "limit": limit,
                "apikey": self.api_key
            }
            
            response = self.client.get(
                self.base_url,
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"Alpha Vantage API error for {symbol}: {response.status_code}")
                return []  # Return empty list instead of mock data
            
            data = response.json()
            
            if "feed" not in data:
                print(f"No news feed found for {symbol}")
                return []  # Return empty list instead of mock data
            
            news = []
            for article in data["feed"][:limit]:
                # Extract sentiment data
                sentiment_score = 0.0
                direction = "neutral"
                
                if "ticker_sentiment" in article:
                    for ticker_sentiment in article["ticker_sentiment"]:
                        if ticker_sentiment.get("ticker") == symbol:
                            sentiment_score = float(ticker_sentiment.get("relevance_score", 0)) * \
                                            float(ticker_sentiment.get("ticker_sentiment_score", 0))
                            
                            # Convert sentiment score to direction
                            if sentiment_score > 0.1:
                                direction = "buy"
                            elif sentiment_score < -0.1:
                                direction = "sell"
                            else:
                                direction = "neutral"
                            break
                
                # Calculate importance based on overall sentiment score
                overall_sentiment = float(article.get("overall_sentiment_score", 0))
                importance = min(1.0, abs(overall_sentiment) + 0.3)
                
                news.append({
                    "headline": article.get("title", "")[:100],
                    "sentiment": sentiment_score,
                    "direction": direction,
                    "importance": importance,
                    "source": article.get("source", "Unknown"),
                    "url": article.get("url", ""),
                    "published": article.get("time_published", "")
                })
            
            # Cache the results
            self.cache[cache_key] = news
            self.cache_time[cache_key] = time.time()
            
            return news if news else []  # Return empty list if no news found
            
        except Exception as e:
            print(f"Error fetching news for {symbol}: {e}")
            return []  # Return empty list instead of mock data
    
    def get_insider_transactions(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get insider transactions for a symbol
        Returns mock data for demo purposes
        """
        cache_key = f"insider_{symbol}"
        if cache_key in self.cache:
            if time.time() - self.cache_time.get(cache_key, 0) < self.cache_ttl:
                print(f"Using cached insider data for {symbol}")
                return self.cache[cache_key]
        
        # Mock insider data for demo purposes
        print(f"Using mock insider data for {symbol}")
        
        # Generate realistic mock insider data
        import random
        buy_transactions = random.randint(1, 8)
        sell_transactions = random.randint(0, 5)
        
        # Random transaction values
        avg_buy_value = random.uniform(50000, 500000)
        avg_sell_value = random.uniform(30000, 300000)
        
        total_buy_value = buy_transactions * avg_buy_value
        total_sell_value = sell_transactions * avg_sell_value
        
        # Calculate sentiment based on activity
        if total_buy_value > total_sell_value * 1.3:  # 30% more buying
            insider_sentiment = 0.6
            direction = "buy"
        elif total_sell_value > total_buy_value * 1.3:  # 30% more selling
            insider_sentiment = -0.6
            direction = "sell"
        else:
            insider_sentiment = 0.0
            direction = "neutral"
        
        result = {
            "symbol": symbol,
            "insider_sentiment": insider_sentiment,
            "direction": direction,
            "total_buy_value": total_buy_value,
            "total_sell_value": total_sell_value,
            "buy_transactions": buy_transactions,
            "sell_transactions": sell_transactions,
            "recent_transactions": []  # Mock data, no detail needed
        }
        
        # Cache the results
        self.cache[cache_key] = result
        self.cache_time[cache_key] = time.time()
        
        return result
    
    def close(self):
        """Close HTTP client"""
        self.client.close()

# Singleton
_client = None

def get_client() -> AlphaVantageClient:
    global _client
    if _client is None:
        _client = AlphaVantageClient()
    return _client