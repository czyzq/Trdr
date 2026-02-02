"""
Realistic price feed for CFD instruments
Uses current real market prices with small random variations
"""
import random
from datetime import datetime
from typing import Dict, Any

# Base prices updated as of Feb 2, 2026
# Prices match XTB CFD broker values
BASE_PRICES = {
    "GC=F": 4779.0,    # Gold CFD (XTB GOLD)
    "SI=F": 83.040,    # Silver CFD (XTB SILVER - per 100oz?)
    "NQ=F": 25494.0,   # Nasdaq-100 CFD (XTB US100)
}

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
            "GC=F": random.randint(50000, 150000),
            "SI=F": random.randint(100000, 300000),
            "NQ=F": random.randint(1000000, 3000000),
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
        Generate realistic historical candles
        """
        if symbol not in BASE_PRICES:
            return None
        
        base_price = BASE_PRICES[symbol]
        candles = []
        
        # Generate candles going backwards in time
        for i in range(count):
            # Price walks randomly around base price
            price_offset = (i - count/2) * 0.001  # Slight trend
            noise = random.uniform(-0.01, 0.01)
            close = base_price * (1 + price_offset + noise)
            
            candles.append({
                "timestamp": datetime.utcnow().isoformat(),
                "open": close * (1 + random.uniform(-0.002, 0.002)),
                "high": close * (1 + random.uniform(0.001, 0.005)),
                "low": close * (1 - random.uniform(0.001, 0.005)),
                "close": close,
                "volume": random.randint(10000, 100000)
            })
        
        return candles

# Singleton instance
_feeder = None

def get_feeder() -> RealisticPriceFeeder:
    global _feeder
    if _feeder is None:
        _feeder = RealisticPriceFeeder()
    return _feeder
