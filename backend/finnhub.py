"""
Finnhub API client wrapper for fetching CFD price data
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import httpx
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
BASE_URL = "https://finnhub.io/api/v1"

# Instruments we track
INSTRUMENTS = {
    "GC=F": "Gold",
    "SI=F": "Silver",
    "NQ=F": "Nasdaq-100"
}

class FinnhubClient:
    def __init__(self, api_key: str = FINNHUB_API_KEY):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.client = httpx.Client()
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current quote for an instrument
        """
        try:
            params = {
                "symbol": symbol,
                "token": self.api_key
            }
            response = self.client.get(f"{self.base_url}/quote", params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data or "c" not in data:
                return None
            
            return {
                "symbol": symbol,
                "price": data["c"],  # current price
                "high": data["h"],   # high price of day
                "low": data["l"],    # low price of day
                "open": data["o"],   # open price
                "volume": data.get("v", 0),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            print(f"Error fetching quote for {symbol}: {e}")
            return None
    
    def get_candles(
        self, 
        symbol: str, 
        resolution: str = "60",  # 1, 5, 15, 30, 60, D, W, M
        count: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch candlestick data
        """
        try:
            # Calculate from timestamp (count bars back)
            now = datetime.utcnow()
            if resolution == "D":
                from_dt = now - timedelta(days=count)
            elif resolution == "W":
                from_dt = now - timedelta(weeks=count)
            elif resolution == "M":
                from_dt = now - timedelta(days=count*30)
            else:
                minutes = int(resolution)
                from_dt = now - timedelta(minutes=minutes*count)
            
            params = {
                "symbol": symbol,
                "resolution": resolution,
                "from": int(from_dt.timestamp()),
                "to": int(now.timestamp()),
                "token": self.api_key
            }
            
            response = self.client.get(f"{self.base_url}/forex/candle", params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("s") == "no_data":
                return None
            
            candles = []
            for i in range(len(data.get("o", []))):
                candles.append({
                    "timestamp": datetime.fromtimestamp(data["t"][i]).isoformat(),
                    "open": data["o"][i],
                    "high": data["h"][i],
                    "low": data["l"][i],
                    "close": data["c"][i],
                    "volume": data.get("v", [0])[i] if "v" in data else 0
                })
            
            return candles
        except Exception as e:
            print(f"Error fetching candles for {symbol}: {e}")
            return None
    
    def get_company_news(self, symbol: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch company/market news for sentiment analysis
        """
        try:
            params = {
                "symbol": symbol,
                "limit": limit,
                "token": self.api_key
            }
            response = self.client.get(f"{self.base_url}/company-news", params=params)
            response.raise_for_status()
            data = response.json()
            
            if not isinstance(data, list):
                return None
            
            news = []
            for article in data[:limit]:
                news.append({
                    "headline": article.get("headline"),
                    "summary": article.get("summary"),
                    "source": article.get("source"),
                    "url": article.get("url"),
                    "image": article.get("image"),
                    "datetime": datetime.fromtimestamp(article.get("datetime", 0)).isoformat()
                })
            
            return news
        except Exception as e:
            print(f"Error fetching news for {symbol}: {e}")
            return None
    
    def close(self):
        """Close the HTTP client"""
        self.client.close()

# Singleton instance
_client = None

def get_client() -> FinnhubClient:
    global _client
    if _client is None:
        _client = FinnhubClient()
    return _client
