"""
Historical data fetcher for backtesting.

Sources:
  1. Yahoo Finance REST API (free, no key required) — via httpx
  2. CSV files (for offline/reproducible backtests)
  3. Alpha Vantage (already integrated, but rate-limited)

Yahoo Finance symbol mapping for our instruments:
  XAU  -> GC=F   (COMEX Gold Futures — tracks gold spot price directly)
  XAG  -> SI=F   (COMEX Silver Futures — tracks silver spot price directly)
  US100 -> NQ=F  (E-mini Nasdaq-100 Futures — tracks Nasdaq-100 index)
  BTC  -> BTC-USD (Bitcoin in USD)
"""

import csv
import io
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import httpx


# Yahoo Finance symbol mapping — uses futures/forex for accurate CFD prices
YAHOO_SYMBOL_MAP = {
    "XAU": "GC=F",      # COMEX Gold Futures (trades near gold spot ~$2000+)
    "XAG": "SI=F",      # COMEX Silver Futures (trades near silver spot ~$25+)
    "US100": "NQ=F",    # E-mini Nasdaq-100 Futures (tracks index ~$20000+)
    "BTC": "BTC-USD",   # Bitcoin in USD
}

# Price multipliers: futures trade at actual commodity/index prices, no scaling needed
PRICE_MULTIPLIERS = {
    "XAU": 1.0,     # GC=F trades at gold spot price directly
    "XAG": 1.0,     # SI=F trades at silver spot price directly
    "US100": 1.0,   # NQ=F trades at Nasdaq-100 index level directly
    "BTC": 1.0,     # BTC-USD is the actual price
}


def fetch_yahoo_historical(
    symbol: str,
    period_days: int = 365,
    interval: str = "1d",
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch historical OHLCV data from Yahoo Finance.

    Args:
        symbol: Internal symbol (XAU, XAG, US100, BTC)
        period_days: How many days of history to fetch
        interval: Candle interval — "1d", "1h", "5m", "15m", "30m", "60m"
                  Note: intraday data (< 1d) is limited to last 60 days on Yahoo.

    Returns:
        List of candle dicts with keys: timestamp, time, open, high, low, close, volume
        Sorted oldest-first (chronological order).
    """
    yahoo_sym = YAHOO_SYMBOL_MAP.get(symbol, symbol)
    multiplier = PRICE_MULTIPLIERS.get(symbol, 1.0)

    end_ts = int(time.time())
    start_ts = end_ts - (period_days * 86400)

    # Try Yahoo Finance v8 chart JSON API first (more reliable than CSV download)
    chart_url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_sym}"
        f"?period1={start_ts}&period2={end_ts}&interval={interval}"
        f"&includePrePost=false"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    }

    try:
        with httpx.Client(follow_redirects=True) as client:
            resp = client.get(chart_url, headers=headers, timeout=30)
            resp.raise_for_status()

        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            raise ValueError("Empty chart result")

        timestamps = result[0].get("timestamp", [])
        quote = result[0].get("indicators", {}).get("quote", [{}])[0]
        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        candles = []
        for i, ts in enumerate(timestamps):
            try:
                o = opens[i]
                h = highs[i]
                l = lows[i]
                c = closes[i]
                v = volumes[i]
                if any(x is None for x in (o, h, l, c)):
                    continue
                dt = datetime.utcfromtimestamp(ts)
                candles.append({
                    "timestamp": dt.isoformat(),
                    "time": dt.strftime("%m/%d") if interval.endswith("d") else dt.strftime("%H:%M"),
                    "open": round(o * multiplier, 2),
                    "high": round(h * multiplier, 2),
                    "low": round(l * multiplier, 2),
                    "close": round(c * multiplier, 2),
                    "volume": int(v or 0),
                })
            except (IndexError, TypeError):
                continue

        return candles if candles else None

    except Exception as e:
        print(f"[HistoricalData] Yahoo chart API failed for {symbol} ({yahoo_sym}): {e}")

    # Fallback: try CSV download endpoint
    csv_url = (
        f"https://query1.finance.yahoo.com/v7/finance/download/{yahoo_sym}"
        f"?period1={start_ts}&period2={end_ts}&interval={interval}"
        f"&events=history&includeAdjustedClose=true"
    )

    try:
        with httpx.Client(follow_redirects=True) as client:
            resp = client.get(csv_url, headers=headers, timeout=30)
            resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        candles = []

        for row in reader:
            try:
                if row.get("Close") in (None, "", "null"):
                    continue
                dt = datetime.strptime(row["Date"], "%Y-%m-%d")
                candles.append({
                    "timestamp": dt.isoformat(),
                    "time": dt.strftime("%m/%d"),
                    "open": round(float(row["Open"]) * multiplier, 2),
                    "high": round(float(row["High"]) * multiplier, 2),
                    "low": round(float(row["Low"]) * multiplier, 2),
                    "close": round(float(row["Close"]) * multiplier, 2),
                    "volume": int(float(row["Volume"])),
                })
            except (ValueError, KeyError):
                continue

        return candles if candles else None

    except Exception as e:
        print(f"[HistoricalData] Yahoo CSV download also failed for {symbol} ({yahoo_sym}): {e}")
        return None


def load_csv_candles(filepath: str, multiplier: float = 1.0) -> Optional[List[Dict[str, Any]]]:
    """
    Load OHLCV candles from a CSV file.

    Expected CSV columns: Date, Open, High, Low, Close, Volume
    (same format as Yahoo Finance download).
    """
    if not os.path.exists(filepath):
        print(f"[HistoricalData] CSV file not found: {filepath}")
        return None

    candles = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                if row.get("Close") in (None, "", "null"):
                    continue
                # Try multiple date formats
                date_str = row.get("Date") or row.get("date") or row.get("Datetime")
                for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    continue

                candles.append({
                    "timestamp": dt.isoformat(),
                    "time": dt.strftime("%m/%d") if dt.hour == 0 else dt.strftime("%H:%M"),
                    "open": round(float(row["Open"]) * multiplier, 2),
                    "high": round(float(row["High"]) * multiplier, 2),
                    "low": round(float(row["Low"]) * multiplier, 2),
                    "close": round(float(row["Close"]) * multiplier, 2),
                    "volume": int(float(row.get("Volume", 0))),
                })
            except (ValueError, KeyError):
                continue

    return candles if candles else None


def fetch_alpha_vantage_historical(
    symbol: str,
    count: int = 200,
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch daily historical data from Alpha Vantage (uses project's API key).
    Provides up to ~100 trading days of data on free tier.
    Requires ALPHA_VANTAGE_API_KEY in .env.
    """
    try:
        from alpha_vantage import get_client
        client = get_client()
        candles = client.get_candles(symbol, resolution="D", count=count)
        if candles:
            result = []
            for c in candles:
                ts = c.get("timestamp", "")
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else datetime.now()
                except ValueError:
                    dt = datetime.now()
                result.append({
                    "timestamp": dt.isoformat(),
                    "time": dt.strftime("%m/%d"),
                    "open": round(c["open"], 2),
                    "high": round(c["high"], 2),
                    "low": round(c["low"], 2),
                    "close": round(c["close"], 2),
                    "volume": c.get("volume", 0),
                })
            return result if result else None
    except Exception as e:
        print(f"[HistoricalData] Alpha Vantage failed for {symbol}: {e}")
    return None


def fetch_from_db_cache(
    symbol: str,
    resolution: str = "D",
) -> Optional[List[Dict[str, Any]]]:
    """
    Load previously cached real candle data from MongoDB.
    This uses data that was fetched and saved by the running app.
    """
    try:
        import database as db
        cached = db.load_candles(symbol, resolution)
        if cached and cached.get("candles"):
            candles = cached["candles"]
            print(f"[HistoricalData] Loaded {len(candles)} cached candles from DB "
                  f"(source: {cached.get('source', '?')}, fetched: {cached.get('fetched_at', '?')})")
            return candles
    except Exception as e:
        print(f"[HistoricalData] DB cache load failed for {symbol}: {e}")
    return None


def generate_sample_data(
    symbol: str = "XAU",
    days: int = 200,
    base_price: float = 2000.0,
    resolution: str = "D",
) -> List[Dict[str, Any]]:
    """
    Generate deterministic sample OHLCV data for testing (no API needed).
    Uses a simple random walk with a fixed seed for reproducibility.

    Args:
        resolution: "D" for daily, or "1"/"5"/"15"/"30"/"60" for intraday.
                    Intraday generates candles within market hours (9:30-16:00
                    for equities/commodities, 24h for BTC) over the specified
                    number of trading days.
    """
    import random
    rng = random.Random(42 + hash(symbol))

    candles = []
    price = base_price
    start_date = datetime(2025, 1, 2)

    if resolution == "D":
        for i in range(days):
            dt = start_date + timedelta(days=i)
            if symbol in ("US100", "XAU", "XAG") and dt.weekday() >= 5:
                continue

            change_pct = rng.gauss(0.0002, 0.012)
            price *= (1 + change_pct)
            price = max(price * 0.5, price)

            open_price = price * (1 + rng.uniform(-0.003, 0.003))
            high = max(open_price, price) * (1 + rng.uniform(0.001, 0.008))
            low = min(open_price, price) * (1 - rng.uniform(0.001, 0.008))

            candles.append({
                "timestamp": dt.isoformat(),
                "time": dt.strftime("%m/%d"),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(price, 2),
                "volume": rng.randint(50000, 200000),
            })
    else:
        # Intraday candles
        interval_minutes = int(resolution)

        # Market hours by instrument
        if symbol == "BTC":
            market_open_h, market_open_m = 0, 0
            market_close_h, market_close_m = 23, 59
        else:
            market_open_h, market_open_m = 9, 30
            market_close_h, market_close_m = 16, 0

        # Volatility scales down with shorter intervals
        vol_scale = {
            "1": 0.001, "5": 0.002, "15": 0.003, "30": 0.004, "60": 0.006,
        }.get(resolution, 0.003)

        for d in range(days):
            dt_day = start_date + timedelta(days=d)
            if symbol in ("US100", "XAU", "XAG") and dt_day.weekday() >= 5:
                continue

            current_dt = dt_day.replace(
                hour=market_open_h, minute=market_open_m, second=0
            )
            close_dt = dt_day.replace(
                hour=market_close_h, minute=market_close_m, second=0
            )

            while current_dt < close_dt:
                change_pct = rng.gauss(0.00005, vol_scale)
                price *= (1 + change_pct)
                price = max(base_price * 0.5, price)

                open_price = price * (1 + rng.uniform(-vol_scale * 0.3, vol_scale * 0.3))
                high = max(open_price, price) * (1 + rng.uniform(0.0005, vol_scale))
                low = min(open_price, price) * (1 - rng.uniform(0.0005, vol_scale))

                candles.append({
                    "timestamp": current_dt.isoformat(),
                    "time": current_dt.strftime("%H:%M"),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(price, 2),
                    "volume": rng.randint(10000, 80000),
                })

                current_dt += timedelta(minutes=interval_minutes)

    return candles
