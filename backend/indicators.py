"""
Technical indicators for CFD signal generation
RSI, MACD, ATR
"""
from typing import List, Dict, Optional, Tuple

class TechnicalIndicators:
    """Calculate technical indicators from price data"""
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """
        Relative Strength Index
        Returns value between 0 and 100
        """
        if len(prices) < period + 1:
            return None
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100 if avg_gain > 0 else 50
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[Dict[str, float]]:
        """
        MACD (Moving Average Convergence Divergence)
        Returns dict with macd_line, signal_line, histogram
        """
        if len(prices) < slow + signal - 1:
            return None
        
        # Calculate EMAs
        ema_fast = TechnicalIndicators._ema(prices, fast)
        ema_slow = TechnicalIndicators._ema(prices, slow)
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line (EMA of MACD)
        # Get last (slow - 1) values from macd_line for signal calculation
        macd_values = []
        for i in range(len(prices) - slow + 1, len(prices) + 1):
            ema_f = TechnicalIndicators._ema(prices[:i], fast)
            ema_s = TechnicalIndicators._ema(prices[:i], slow)
            macd_values.append(ema_f - ema_s)
        
        signal_line = TechnicalIndicators._ema(macd_values, signal) if len(macd_values) >= signal else None
        histogram = macd_line - (signal_line if signal_line else 0) if signal_line else None
        
        return {
            "macd_line": macd_line,
            "signal_line": signal_line,
            "histogram": histogram
        }
    
    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
        """
        Average True Range - volatility indicator
        """
        if len(highs) < period:
            return None
        
        trs = []
        for i in range(1, len(highs)):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i-1])
            lc = abs(lows[i] - closes[i-1])
            tr = max(hl, hc, lc)
            trs.append(tr)
        
        # Calculate ATR using SMA of TR
        atr_value = sum(trs[-period:]) / period
        return atr_value
    
    @staticmethod
    def _ema(prices: List[float], period: int) -> float:
        """Calculate EMA (Exponential Moving Average)"""
        if len(prices) < period:
            return sum(prices) / len(prices)  # Fallback to SMA
        
        multiplier = 2 / (period + 1)
        
        # SMA for first point
        ema = sum(prices[:period]) / period
        
        # EMA for remaining points
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    @staticmethod
    def sma(prices: List[float], period: int) -> Optional[float]:
        """Simple Moving Average"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    @staticmethod
    def bollinger_bands(
        prices: List[float], 
        period: int = 20, 
        std_dev: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """
        Bollinger Bands
        Returns upper, middle (SMA), lower bands
        """
        if len(prices) < period:
            return None
        
        # Middle band (SMA)
        middle = sum(prices[-period:]) / period
        
        # Standard deviation
        variance = sum((p - middle) ** 2 for p in prices[-period:]) / period
        std = variance ** 0.5
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "std_dev": std
        }
    
    @staticmethod
    def momentum(prices: List[float], period: int = 10) -> Optional[float]:
        """Momentum indicator - rate of change"""
        if len(prices) < period + 1:
            return None
        return prices[-1] - prices[-period-1]
    
    @staticmethod
    def calculate_all(
        candles: List[Dict],
        period: int = 14
    ) -> Optional[Dict]:
        """
        Calculate all indicators from candlestick data
        """
        if not candles or len(candles) < max(26, period):
            return None
        
        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        
        return {
            "rsi_14": TechnicalIndicators.rsi(closes, 14),
            "macd": TechnicalIndicators.macd(closes),
            "atr_14": TechnicalIndicators.atr(highs, lows, closes, 14),
            "bollinger_bands": TechnicalIndicators.bollinger_bands(closes),
            "momentum_10": TechnicalIndicators.momentum(closes, 10),
            "sma_20": TechnicalIndicators.sma(closes, 20),
            "sma_50": TechnicalIndicators.sma(closes, 50),
        }
