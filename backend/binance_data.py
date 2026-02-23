"""Binance API for fetching historical candle data"""
import requests
from typing import List, Dict, Optional
import time


BINANCE_BASE = "https://api.binance.com/api/v3"

# Map our resolutions to Binance intervals
RESOLUTION_MAP = {
    "1": "1m",
    "5": "5m",
    "15": "15m", 
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "D": "1d",
    "1h": "1h",
}

# Binance symbol mapping
SYMBOL_MAP = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "XAU": "XAUUSDT",
    "XAG": "XAGUSDT",
    "US100": "US100USDT",  # May not exist
    "SPX": "SPXUSDT",
}


def get_binance_symbol(symbol: str) -> str:
    """Map our symbol to Binance symbol"""
    # Already in Binance format
    if symbol.upper().endswith("USDT"):
        return symbol.upper()
    return SYMBOL_MAP.get(symbol, f"{symbol}USDT")


def fetch_binance_candles(
    symbol: str,
    interval: str = "1h",
    start_time: int = None,
    end_time: int = None,
    limit: int = 1000
) -> List[Dict]:
    """Fetch candles from Binance"""
    binance_symbol = get_binance_symbol(symbol)
    
    url = f"{BINANCE_BASE}/klines"
    params = {
        "symbol": binance_symbol,
        "interval": interval,
        "limit": limit,
    }
    
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        candles = []
        for c in data:
            # Convert timestamp from ms to ISO format
            from datetime import datetime
            ts = datetime.utcfromtimestamp(c[0] / 1000).strftime("%Y-%m-%dT%H:%M:%SZ")
            candles.append({
                "timestamp": ts,
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })
        
        return candles
    except Exception as e:
        print(f"[Binance] Error fetching {symbol}: {e}")
        return []


def fetch_binance_historical(
    symbol: str,
    resolution: str = "60",
    days: int = 30,
    end_timestamp: int = None,
) -> List[Dict]:
    """Fetch historical candles for a symbol"""
    import datetime
    
    interval = RESOLUTION_MAP.get(resolution, "1h")
    
    # Calculate start time
    if end_timestamp is None:
        end_timestamp = int(time.time() * 1000)
    
    start_timestamp = end_timestamp - (days * 24 * 60 * 60 * 1000)
    
    all_candles = []
    current_start = start_timestamp
    
    # Binance max limit is 1000, so we may need multiple calls
    while current_start < end_timestamp:
        candles = fetch_binance_candles(
            symbol,
            interval=interval,
            start_time=current_start,
            end_time=end_timestamp,
            limit=1000
        )
        
        if not candles:
            break
        
        all_candles.extend(candles)
        
        # Move to next batch
        last_timestamp = candles[-1]["timestamp"]
        # Parse timestamp - could be ISO string or epoch
        if isinstance(last_timestamp, str):
            # Parse ISO format "2026-02-18T22:50:00Z"
            from datetime import datetime as dt_module
            dt = dt_module.fromisoformat(last_timestamp.replace("Z", "+00:00"))
            last_timestamp = int(dt.timestamp() * 1000)
        if last_timestamp >= end_timestamp:
            break
        current_start = last_timestamp + 1  # +1ms to avoid duplicates
    
    return all_candles
