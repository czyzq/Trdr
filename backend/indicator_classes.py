"""
Indicator classes for CFD trading bot
Each indicator is a class with default settings
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from indicators import TechnicalIndicators


class Indicator(ABC):
    """Base class for all technical indicators"""
    
    id: str = ""           # Unique identifier (RSI, MACD, BB, etc.)
    name: str = ""         # Display name
    description: str = ""  # Description
    default_params: dict = {}  # Default parameters
    
    @abstractmethod
    def calculate(self, candles: List[Dict], params: dict = None) -> Optional[Any]:
        """
        Calculate indicator value from candles
        Returns indicator value(s) in format expected by strategies
        """
        pass
    
    def get_value(self, indicators_result: Dict, prefix: str = None) -> Optional[Any]:
        """Get this indicator's value from full indicators result dict"""
        key = prefix or self.id.lower()
        # Map common keys
        key_map = {
            "RSI": "rsi_14",
            "MACD": "macd",
            "BB": "bollinger_bands",
            "SMA": "sma_20",
            "ADX": "adx",
            "STOCH": "stoch_rsi",
            "MOMENTUM": "momentum_10",
        }
        return indicators_result.get(key_map.get(self.id, key.lower()))


class RSI(Indicator):
    id = "RSI"
    name = "Relative Strength Index"
    description = "Momentum oscillator measuring speed and change of price movements (0-100)"
    default_params = {
        "period": 14,
        "overbought": 70,
        "oversold": 30,
    }
    
    def calculate(self, candles: List[Dict], params: dict = None) -> Optional[float]:
        params = params or self.default_params
        closes = [c["close"] for c in candles]
        return TechnicalIndicators.rsi(closes, params.get("period", 14))


class MACD(Indicator):
    id = "MACD"
    name = "Moving Average Convergence Divergence"
    description = "Trend-following momentum indicator showing relationship between two EMAs"
    default_params = {
        "fast": 12,
        "slow": 26,
        "signal": 9,
    }
    
    def calculate(self, candles: List[Dict], params: dict = None) -> Optional[Dict]:
        params = params or self.default_params
        closes = [c["close"] for c in candles]
        return TechnicalIndicators.macd(
            closes,
            params.get("fast", 12),
            params.get("slow", 26),
            params.get("signal", 9)
        )


class BollingerBands(Indicator):
    id = "BB"
    name = "Bollinger Bands"
    description = "Volatility bands above and below a moving average"
    default_params = {
        "period": 20,
        "std": 2,
    }
    
    def calculate(self, candles: List[Dict], params: dict = None) -> Optional[Dict]:
        params = params or self.default_params
        closes = [c["close"] for c in candles]
        return TechnicalIndicators.bollinger_bands(
            closes,
            params.get("period", 20),
            params.get("std", 2)
        )


class SMA(Indicator):
    id = "SMA"
    name = "Simple Moving Average"
    description = "Average price over a specified number of periods"
    default_params = {
        "period": 20,
        "period2": 50,  # For crossover detection
    }
    
    def calculate(self, candles: List[Dict], params: dict = None) -> Optional[Dict]:
        params = params or self.default_params
        closes = [c["close"] for c in candles]
        period = params.get("period", 20)
        
        sma_value = TechnicalIndicators.sma(closes, period)
        if sma_value is None:
            return None
        
        # Also calculate second SMA if configured
        sma2_value = None
        period2 = params.get("period2")
        if period2:
            sma2_value = TechnicalIndicators.sma(closes, period2)
        
        return {
            "sma": sma_value,
            "sma2": sma2_value,
        }


class ADX(Indicator):
    id = "ADX"
    name = "Average Directional Index"
    description = "Measures trend strength without regard to direction"
    default_params = {
        "period": 14,
    }
    
    def calculate(self, candles: List[Dict], params: dict = None) -> Optional[Dict]:
        params = params or self.default_params
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        closes = [c["close"] for c in candles]
        return TechnicalIndicators.adx(
            highs, lows, closes,
            params.get("period", 14)
        )


class StochasticRSI(Indicator):
    id = "STOCH"
    name = "Stochastic RSI"
    description = "Stochastic oscillator applied to RSI values"
    default_params = {
        "rsi_period": 14,
        "stoch_period": 14,
    }
    
    def calculate(self, candles: List[Dict], params: dict = None) -> Optional[Dict]:
        params = params or self.default_params
        closes = [c["close"] for c in candles]
        return TechnicalIndicators.stochastic_rsi(
            closes,
            params.get("rsi_period", 14),
            params.get("stoch_period", 14)
        )


class Momentum(Indicator):
    id = "MOMENTUM"
    name = "Momentum"
    description = "Rate of change in price over a period"
    default_params = {
        "period": 10,
    }
    
    def calculate(self, candles: List[Dict], params: dict = None) -> Optional[float]:
        params = params or self.default_params
        closes = [c["close"] for c in candles]
        return TechnicalIndicators.momentum(
            closes,
            params.get("period", 10)
        )


# All available indicators
INDICATORS: Dict[str, type] = {
    "RSI": RSI,
    "MACD": MACD,
    "BB": BollingerBands,
    "SMA": SMA,
    "ADX": ADX,
    "STOCH": StochasticRSI,
    "MOMENTUM": Momentum,
}

# List of all indicator IDs
ALL_INDICATOR_IDS = list(INDICATORS.keys())


def get_indicator(indicator_id: str) -> Optional[Indicator]:
    """Get indicator class by ID"""
    indicator_class = INDICATORS.get(indicator_id)
    if indicator_class:
        return indicator_class()
    return None


def get_indicator_info(indicator_id: str) -> Optional[Dict]:
    """Get indicator metadata"""
    indicator_class = INDICATORS.get(indicator_id)
    if indicator_class:
        return {
            "id": indicator_class.id,
            "name": indicator_class.name,
            "description": indicator_class.description,
            "default_params": indicator_class.default_params,
        }
    return None
