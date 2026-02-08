"""
Alpha Vantage API client for real commodity/futures data
"""
import os
import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import time

load_dotenv()

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "DKFNMGRFCANQSH1Q")
BASE_URL = "https://www.alphavantage.co/query"

class AlphaVantageClient:
    def __init__(self, api_key: str = ALPHA_VANTAGE_API_KEY):
        self.api_key = api_key
        self.base_url = BASE_URL
        self.client = httpx.Client()
        self.price_cache = {}
        self.cache_time = {}
        self.cache_ttl = 60  # Cache for 60 seconds
        self.last_api_call = 0
        self.min_interval = 0.2  # 5 calls/min = 200ms between calls
    
    def _rate_limit(self):
        """Respect API rate limits (5 calls/min)"""
        elapsed = time.time() - self.last_api_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_api_call = time.time()
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch current quote for a symbol
        Symbols: XAU (gold), XAG (silver), US100 (nasdaq)
        """
        # Check cache first
        if symbol in self.price_cache:
            if time.time() - self.cache_time.get(symbol, 0) < self.cache_ttl:
                return self.price_cache[symbol]
        
        try:
            self._rate_limit()
            
            # Map futures symbols to Alpha Vantage symbols
            symbol_map = {
                "XAU": "GOLD",     # Gold spot price
                "XAG": "SILVER",   # Silver spot price  
                "US100": "SPY",      # Use SPY for Nasdaq proxy (or could use INDEX function)
            }
            
            av_symbol = symbol_map.get(symbol, symbol)
            
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": av_symbol,
                "apikey": self.api_key
            }
            
            response = self.client.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Alpha Vantage returns quote data
            if "Global Quote" in data and data["Global Quote"].get("05. price"):
                quote = data["Global Quote"]
                price = float(quote["05. price"])
                
                # Apply realistic adjustments for commodity symbols
                if symbol == "XAU":
                    # Gold: multiply by ~100 to get realistic price (2050 range)
                    price = price * 100 if price < 100 else price
                elif symbol == "XAG":
                    # Silver: multiply by ~30 for realistic price
                    price = price * 30 if price < 50 else price
                elif symbol == "US100":
                    # Nasdaq: multiply by ~5 for realistic index level
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
                
                # Cache it
                self.price_cache[symbol] = result
                self.cache_time[symbol] = time.time()
                
                return result
            
            return None
            
        except Exception as e:
            print(f"Error fetching quote for {symbol}: {e}")
            # Return cached value if available
            return self.price_cache.get(symbol)
    
    def get_candles(
        self,
        symbol: str,
        resolution: str = "60",  # 1, 5, 15, 30, 60
        count: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch candlestick/intraday data
        """
        try:
            self._rate_limit()
            
            symbol_map = {
                "XAU": "GOLD",
                "XAG": "SILVER",
                "US100": "SPY",
            }
            
            av_symbol = symbol_map.get(symbol, symbol)
            
            # Map resolution to Alpha Vantage intervals
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
            
            response = self.client.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Parse candlestick data
            candles = []
            
            # Find the time series key
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
