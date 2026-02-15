"""
Alpha Vantage API client for real commodity/futures data - ASYNC version
"""
import os
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import time

load_dotenv()

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
BASE_URL = "https://www.alphavantage.co/query"


class AsyncAlphaVantageClient:
    """Fully async Alpha Vantage client."""
    
    def __init__(self, api_key: str = ALPHA_VANTAGE_API_KEY):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.client = httpx.AsyncClient(timeout=10)
        self.price_cache = {}
        self.cache_time = {}
        self.cache_ttl = 60  # Cache for 60 seconds
        self.last_api_call = 0
        self.min_interval = 0.05  # 50ms between calls
        self._lock = asyncio.Lock()
    
    async def _rate_limit(self):
        """Async rate limiter."""
        async with self._lock:
            elapsed = time.time() - self.last_api_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_api_call = time.time()
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch current quote for a symbol - ASYNC."""
        # Check cache first
        if symbol in self.price_cache:
            if time.time() - self.cache_time.get(symbol, 0) < self.cache_ttl:
                return self.price_cache[symbol]
        
        try:
            await self._rate_limit()
            
            symbol_map = {
                "XAU": "GOLD",
                "XAG": "SILVER",
                "US100": "QQQ",
            }
            
            av_symbol = symbol_map.get(symbol, symbol)
            
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": av_symbol,
                "apikey": self.api_key
            }
            
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "Global Quote" in data and data["Global Quote"].get("05. price"):
                quote = data["Global Quote"]
                price = float(quote["05. price"])
                
                if symbol == "XAU":
                    price = price * 100 if price < 100 else price
                elif symbol == "XAG":
                    price = price * 30 if price < 50 else price
                elif symbol == "US100":
                    price = price * 5 if price < 10000 else price
                
                result = {
                    "symbol": symbol,
                    "price": price,
                    "high": float(quote.get("09. change", price)) + price,
                    "low": float(quote.get("09. change", 0)) - price * 0.01,
                    "open": price,
                    "volume": int(quote.get("06. volume", 0)),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                self.price_cache[symbol] = result
                self.cache_time[symbol] = time.time()
                
                return result
            
            return None
            
        except Exception as e:
            print(f"Error fetching quote for {symbol}: {e}")
            return self.price_cache.get(symbol)
    
    async def get_candles(
        self,
        symbol: str,
        resolution: str = "60",
        count: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch candlestick data - ASYNC."""
        try:
            await self._rate_limit()
            
            symbol_map = {
                "XAU": "GOLD",
                "XAG": "SILVER",
                "US100": "QQQ",
            }
            
            av_symbol = symbol_map.get(symbol, symbol)
            
            interval_map = {
                "1": "1min",
                "5": "5min",
                "15": "15min",
                "30": "30min",
                "60": "60min",
                "D": "daily",
            }
            
            interval = interval_map.get(resolution, "60min")
            function = "TIME_SERIES_INTRADAY" if resolution != "D" else "TIME_SERIES_DAILY"
            
            params = {
                "function": function,
                "symbol": av_symbol,
                "apikey": self.api_key
            }
            
            if function == "TIME_SERIES_INTRADAY":
                params["interval"] = interval
            
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            candles = []
            ts_key = None
            for key in data.keys():
                if key.startswith("Time Series"):
                    ts_key = key
                    break
            
            if ts_key and isinstance(data[ts_key], dict):
                timestamps = sorted(data[ts_key].keys(), reverse=True)[:count]
                for ts in reversed(timestamps):
                    ohlc = data[ts_key][ts]
                    candles.append({
                        "timestamp": ts,
                        "open": float(ohlc.get("1. open", 0)),
                        "high": float(ohlc.get("2. high", 0)),
                        "low": float(ohlc.get("3. low", 0)),
                        "close": float(ohlc.get("4. close", 0)),
                        "volume": int(ohlc.get("5. volume", 0))
                    })
            
            return candles if candles else None
            
        except Exception as e:
            print(f"Error fetching candles for {symbol}: {e}")
            return None
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Keep old sync client for backward compatibility
class AlphaVantageClient:
    """Legacy sync client - delegates to async client via run_sync."""
    
    def __init__(self, api_key: str = ALPHA_VANTAGE_API_KEY):
        self._async_client = AsyncAlphaVantageClient(api_key)
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Sync wrapper for async get_quote."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in async context - use run_coroutine_threadsafe
                future = asyncio.run_coroutine_threadsafe(
                    self._async_client.get_quote(symbol), loop
                )
                return future.result(timeout=10)
            else:
                return loop.run_until_complete(self._async_client.get_quote(symbol))
        except Exception as e:
            print(f"Error in get_quote: {e}")
            return None
    
    def get_candles(self, symbol: str, resolution: str = "60", count: int = 100):
        """Sync wrapper for async get_candles."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    self._async_client.get_candles(symbol, resolution, count), loop
                )
                return future.result(timeout=10)
            else:
                return loop.run_until_complete(
                    self._async_client.get_candles(symbol, resolution, count)
                )
        except Exception as e:
            print(f"Error in get_candles: {e}")
            return None
    
    def close(self):
        pass  # Async client handles its own lifecycle


# Singletons
_client = None
_async_client = None


def get_client() -> AlphaVantageClient:
    """Get sync client (legacy)."""
    global _client
    if _client is None:
        _client = AlphaVantageClient()
    return _client


def get_async_client() -> AsyncAlphaVantageClient:
    """Get async client (preferred)."""
    global _async_client
    if _async_client is None:
        _async_client = AsyncAlphaVantageClient()
    return _async_client
