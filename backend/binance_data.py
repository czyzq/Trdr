"""Binance API for fetching historical candle data"""
import requests
from typing import List, Dict, Optional
import time
from datetime import datetime, timezone


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


def fetch_binance_history(
    symbol: str = "BTCUSDT",
    interval: str = "5m",
    days: int = 730,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
    page_limit: int = 1000,
    sleep_seconds: float = 0.15,
) -> List[Dict]:
    """Fetch YEARS of kline history by paginating GET /api/v3/klines.

    Walks startTime forward from (now - days) to now, 1000 candles per request,
    sleeping between pages to respect public rate limits. Each page gets one
    retry on failure; on repeated failure the candles collected so far are
    returned. Output is ascending and deduped on the kline OPEN time, in the
    same dict shape used across the codebase.
    """
    binance_symbol = get_binance_symbol(symbol)
    url = f"{BINANCE_BASE}/klines"

    if end_ms is None:
        end_ms = int(time.time() * 1000)
    if start_ms is None:
        start_ms = end_ms - days * 24 * 60 * 60 * 1000

    candles: List[Dict] = []
    seen_opens = set()
    current = start_ms
    page = 0

    while current < end_ms:
        params = {
            "symbol": binance_symbol,
            "interval": interval,
            "startTime": current,
            "endTime": end_ms,
            "limit": page_limit,
        }

        data = None
        for attempt in range(2):
            try:
                response = requests.get(url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                break
            except Exception as e:
                print(f"[Binance] {binance_symbol} {interval} page {page + 1} "
                      f"attempt {attempt + 1}/2 failed: {e}")
                if attempt == 0:
                    time.sleep(1.0)
        if data is None:
            print(f"[Binance] giving up on {binance_symbol} {interval} - "
                  f"returning {len(candles)} candles collected so far")
            break
        if not data:
            break

        for k in data:
            open_ms = int(k[0])
            if open_ms in seen_opens:
                continue
            seen_opens.add(open_ms)
            ts = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            candles.append({
                "timestamp": ts,
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })

        page += 1
        if page % 50 == 0:
            print(f"[Binance] {binance_symbol} {interval}: page {page}, "
                  f"{len(candles)} candles, up to {candles[-1]['timestamp'] if candles else '?'}")

        newest_open = int(data[-1][0])
        if newest_open + 1 <= current:
            break  # no forward progress - avoid infinite loop
        current = newest_open + 1
        if len(data) < page_limit:
            break  # short page = reached the present

        time.sleep(sleep_seconds)

    candles.sort(key=lambda c: c["timestamp"])
    return candles


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
