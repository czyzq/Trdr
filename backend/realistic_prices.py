"""
Realistic price feed for CFD instruments
Uses current real market prices with small random variations
"""
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

# Base prices updated as of Feb 6, 2026
# Proper trading symbols with current market values
BASE_PRICES = {
    "XAU": 2035.50,   # Gold (XAU/USD) - current ~$2035/oz
    "XAG": 22.85,     # Silver (XAG/USD) - current ~$22.85/oz
    "US100": 17525.0,  # Nasdaq-100 (US100) - current ~17525
    "BTC": 97250.0,    # Bitcoin (BTC/USD) - current ~$97250
}

# Warsaw timezone (UTC+1) for proper local time display
WARSAW_OFFSET = timezone(timedelta(hours=1))  # CET/CEST

class RealisticPriceFeeder:
    """
    Generates realistic prices based on current market values
    with small random movements to simulate real-time price action
    """
    
    def __init__(self):
        self.prices = BASE_PRICES.copy()
        self.last_update = {}
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get realistic quote with small random movements
        """
        if symbol not in BASE_PRICES:
            return None
        
        # Get base price
        base_price = BASE_PRICES[symbol]
        
        # Add small random variation (0.1% to 0.5%)
        variation_pct = random.uniform(-0.005, 0.005)
        current_price = base_price * (1 + variation_pct)
        
        # Store for consistency within same request
        self.prices[symbol] = current_price
        
        # Calculate realistic OHLCV
        high = current_price * 1.003
        low = current_price * 0.997
        open_price = current_price * (1 + random.uniform(-0.002, 0.002))
        
        # Realistic volumes
        volumes = {
            "XAU": random.randint(50000, 150000),
            "XAG": random.randint(100000, 300000),
            "US100": random.randint(1000000, 3000000),
            "BTC": random.randint(500000, 2000000),
        }
        
        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "open": round(open_price, 2),
            "volume": volumes.get(symbol, 100000),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_candles(self, symbol: str, resolution: str = "60", count: int = 100):
        """
        Generate realistic historical candles with perfect continuity
        Each candle's open equals the previous candle's close exactly
        
        Resolution mapping:
        1 = 1 minute
        5 = 5 minutes  
        15 = 15 minutes
        30 = 30 minutes
        60 = 1 hour
        D = daily
        
        Uses Warsaw timezone and generates consistent data based on current time
        """
        if symbol not in BASE_PRICES:
            return None
        
        base_price = BASE_PRICES[symbol]
        candles = []
        
        # Get current time in Warsaw timezone (UTC+1)
        warsaw_now = datetime.now(WARSAW_OFFSET)
        
        # Calculate time interval based on resolution using timedelta
        if resolution == 'D':
            interval = timedelta(days=1)
            # For daily, start from today at midnight Warsaw time
            current_time = warsaw_now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # For intraday, use proper minute intervals
            interval_minutes = int(resolution)
            interval = timedelta(minutes=interval_minutes)
            
            # Round to nearest interval for consistent timestamps
            current_minute = warsaw_now.minute
            rounded_minute = (current_minute // interval_minutes) * interval_minutes
            current_time = warsaw_now.replace(minute=rounded_minute, second=0, microsecond=0)
        
        # Generate consistent price data based on current time seed
        # Use the time hash to ensure same time = same prices
        time_seed = int(current_time.timestamp())
        random.seed(time_seed)

        # Get current price with some variation based on time
        current_price = base_price * (1 + random.uniform(-0.002, 0.002))

        # Generate candles in proper chronological order (oldest to newest) for left-to-right chart display
        # Use rounded current_time so candle timestamps align to interval boundaries
        # e.g. 60m candles: 14:00, 13:00, 12:00 instead of 14:37, 13:37, 12:37
        candles = []

        for i in range(count):
            # Calculate timestamp from oldest (now - total_duration) to newest (now)
            # i=0 = oldest candle, i=count-1 = newest candle (current rounded time)
            candle_time = current_time - (interval * (count - 1 - i))
            
            # Generate OHLCV data (same logic as before)
            close = current_price
            
            # Use candle time as seed for consistency
            candle_seed = int(candle_time.timestamp())
            random.seed(candle_seed)
            
            # Generate realistic price movement
            is_up_candle = random.choice([True, False])
            
            if is_up_candle:
                open_range = close * random.uniform(0.001, 0.005)
                open_price = close - open_range
                high = close * (1 + random.uniform(0.001, 0.003))
                low = open_price * (1 - random.uniform(0.001, 0.003))
            else:
                open_range = close * random.uniform(0.001, 0.005)
                open_price = close + open_range
                high = open_price * (1 + random.uniform(0.001, 0.003))
                low = close * (1 - random.uniform(0.001, 0.003))
            
            # Ensure valid price relationships
            high = max(high, open_price, close)
            low = min(low, open_price, close)
            
            candles.append({
                "timestamp": candle_time.isoformat(),
                "time": self._format_time_for_resolution(candle_time, resolution),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": random.randint(10000, 100000)
            })
            
            # For continuity, this candle's open becomes next candle's close
            current_price = open_price
        
        # Ensure perfect continuity by setting each open to previous close
        for i in range(1, len(candles)):
            prev_close = candles[i-1]["close"]
            candles[i]["open"] = prev_close
            
            # Adjust price relationships to maintain validity
            if candles[i]["low"] > prev_close:
                candles[i]["low"] = prev_close
            if candles[i]["high"] < prev_close:
                candles[i]["high"] = prev_close
        
        # Candles are already in chronological order: oldest first, newest last
        return candles
    
    def _format_time_for_resolution(self, dt: datetime, resolution: str) -> str:
        """Format time based on resolution for proper display in Warsaw timezone"""
        # Ensure dt is timezone-aware in Warsaw offset
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=WARSAW_OFFSET)
        elif dt.tzinfo != WARSAW_OFFSET:
            dt = dt.astimezone(WARSAW_OFFSET)
        
        # Generate actual timestamps based on resolution
        if resolution == '1':
            # For 1min: show actual time like 09:30, 09:31, etc.
            return dt.strftime('%H:%M')
        elif resolution == '5':
            # For 5min: show times like 09:30, 09:35, 09:40, etc.
            return dt.strftime('%H:%M')
        elif resolution == '15':
            # For 15min: show times like 09:30, 09:45, 10:00, etc.
            return dt.strftime('%H:%M')
        elif resolution == '30':
            # For 30min: show times like 09:30, 10:00, 10:30, etc.
            return dt.strftime('%H:%M')
        elif resolution == '60':
            # For 1hour: show times like 09:00, 10:00, 11:00, etc.
            return dt.strftime('%H:%M')
        elif resolution == 'D':
            # For daily: show dates like 02/06, 02/07, etc.
            return dt.strftime('%m/%d')
        else:
            return dt.strftime('%H:%M')

# Singleton instance
_feeder = None

def get_feeder() -> RealisticPriceFeeder:
    global _feeder
    if _feeder is None:
        _feeder = RealisticPriceFeeder()
    return _feeder
