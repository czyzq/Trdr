"""
Technical indicators for CFD signal generation
RSI, MACD, ATR
"""

from typing import Dict, List, Optional, Tuple


class TechnicalIndicators:
    """Calculate technical indicators from price data"""

    # ── Backward compatibility wrapper ─────────────────────────────────────
    def __init__(self, candles: List[Dict] = None):
        """Legacy constructor for backward compatibility with tests."""
        self.candles = candles or []
        self.closes = [c.get("close", c.get("close_price", 0)) for c in self.candles]
        self.highs = [c.get("high", c.get("high_price", 0)) for c in self.candles]
        self.lows = [c.get("low", c.get("low_price", 0)) for c in self.candles]

    def calculate_rsi(self, period: int = 14) -> Dict:
        """Legacy method - returns dict with rsi key."""
        result = TechnicalIndicators.rsi(self.closes, period)
        return {"rsi": result} if result is not None else {"rsi": None}

    def calculate_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """Legacy method."""
        result = TechnicalIndicators.macd(self.closes, fast, slow, signal)
        return result or {}

    def calculate_bollinger_bands(self, period: int = 20, std_dev: float = 2.0) -> Dict:
        """Legacy method."""
        result = TechnicalIndicators.bollinger_bands(self.closes, period, std_dev)
        if not result:
            return {}
        # Map to legacy keys expected by tests
        return {
            "bb_upper": result.get("upper"),
            "bb_middle": result.get("middle"),
            "bb_lower": result.get("lower"),
            "bb_position": result.get("position"),
            "bb_std_dev": result.get("std_dev"),
        }

    def calculate_adx(self, period: int = 14) -> Dict:
        """Legacy method."""
        result = TechnicalIndicators.adx(self.highs, self.lows, self.closes, period)
        return result or {}

    def calculate_sma(self, period: int = 20) -> Dict:
        """Legacy method - returns dict with sma key."""
        result = TechnicalIndicators.sma(self.closes, period)
        return {"sma": result} if result is not None else {"sma": None}

    def calculate_atr(self, period: int = 14) -> Dict:
        """Legacy method."""
        result = TechnicalIndicators.atr(self.highs, self.lows, self.closes, period)
        return {"atr": result} if result is not None else {"atr": None}

    def calculate_stochastic_rsi(self, rsi_period: int = 14, stoch_period: int = 14) -> Dict:
        """Legacy method."""
        result = TechnicalIndicators.stochastic_rsi(self.closes, rsi_period, stoch_period)
        return result or {}

    def calculate_volume_ratio(self, period: int = 20) -> Dict:
        """Legacy method."""
        result = TechnicalIndicators.volume_profile(self.candles, period)
        return result or {}

    def calculate_all_indicators(self, period: int = 14) -> Dict:
        """Legacy method - alias for calculate_all."""
        return TechnicalIndicators.calculate_all(self.candles, period) or {}

    def calculate_all(self, candles=None) -> Dict:
        """Legacy method - calculate all indicators."""
        if candles is None:
            candles = self.candles
        return TechnicalIndicators.calculate_all(candles, 14) or {}

    # ── Additional legacy methods ─────────────────────────────────────────

    def _get_rsi_zone(self, rsi: float) -> str:
        """Get RSI zone - OVERSOLD/NEUTRAL/OVERBOUGHT."""
        if rsi is None:
            return "NEUTRAL"
        if rsi < 30:
            return "OVERSOLD"
        if rsi > 70:
            return "OVERBOUGHT"
        return "NEUTRAL"

    def _get_macd_bullish(self, macd_result: Dict) -> bool:
        """Check if MACD is bullish."""
        if not macd_result:
            return False
        hist = macd_result.get("histogram", 0)
        return hist > 0

    def _get_bb_zone(self, bb_result: Dict) -> str:
        """Get Bollinger Bands zone."""
        if not bb_result:
            return "MIDDLE"
        position = bb_result.get("position", 0.5)
        if position < 0.2:
            return "LOWER"
        if position > 0.8:
            return "UPPER"
        return "MIDDLE"

    def _get_trend(self, adx_result: Dict) -> str:
        """Get trend direction from ADX."""
        if not adx_result:
            return "NEUTRAL"
        if adx_result.get("adx", 0) < 25:
            return "NEUTRAL"
        plus_di = adx_result.get("plus_di", 0)
        minus_di = adx_result.get("minus_di", 0)
        if plus_di > minus_di:
            return "BULLISH"
        if minus_di > plus_di:
            return "BEARISH"
        return "NEUTRAL"

    # ── Static methods ─────────────────────────────────────────────────────

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """
        Relative Strength Index
        Returns value between 0 and 100
        """
        if len(prices) < period + 1:
            return None

        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
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

        return {"macd_line": macd_line, "signal_line": signal_line, "histogram": histogram}

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
            hc = abs(highs[i] - closes[i - 1])
            lc = abs(lows[i] - closes[i - 1])
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
    def bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Optional[Dict[str, float]]:
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
        std = variance**0.5

        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        return {"upper": upper, "middle": middle, "lower": lower, "std_dev": std}

    @staticmethod
    def momentum(prices: List[float], period: int = 10) -> Optional[float]:
        """Momentum indicator - rate of change"""
        if len(prices) < period + 1:
            return None
        return prices[-1] - prices[-period - 1]

    @staticmethod
    def adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[Dict[str, float]]:
        """
        Average Directional Index - measures trend strength (0-100).
        >25 = trending, <20 = ranging.
        Also returns +DI and -DI for direction.
        """
        if len(highs) < period * 2 + 1:
            return None

        plus_dm = []
        minus_dm = []
        tr_list = []

        for i in range(1, len(highs)):
            up = highs[i] - highs[i - 1]
            down = lows[i - 1] - lows[i]

            plus_dm.append(up if up > down and up > 0 else 0)
            minus_dm.append(down if down > up and down > 0 else 0)

            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i - 1])
            lc = abs(lows[i] - closes[i - 1])
            tr_list.append(max(hl, hc, lc))

        def smooth(values: List[float], p: int) -> List[float]:
            result = [sum(values[:p])]
            for v in values[p:]:
                result.append(result[-1] - result[-1] / p + v)
            return result

        smooth_tr = smooth(tr_list, period)
        smooth_plus = smooth(plus_dm, period)
        smooth_minus = smooth(minus_dm, period)

        dx_values = []
        for i in range(len(smooth_tr)):
            if smooth_tr[i] == 0:
                continue
            pdi = 100 * smooth_plus[i] / smooth_tr[i]
            mdi = 100 * smooth_minus[i] / smooth_tr[i]
            denom = pdi + mdi
            if denom > 0:
                dx_values.append(100 * abs(pdi - mdi) / denom)

        if len(dx_values) < period:
            return None

        adx_val = sum(dx_values[:period]) / period
        for dx in dx_values[period:]:
            adx_val = (adx_val * (period - 1) + dx) / period

        last_pdi = 100 * smooth_plus[-1] / smooth_tr[-1] if smooth_tr[-1] else 0
        last_mdi = 100 * smooth_minus[-1] / smooth_tr[-1] if smooth_tr[-1] else 0

        return {
            "adx": round(adx_val, 2),
            "plus_di": round(last_pdi, 2),
            "minus_di": round(last_mdi, 2),
        }

    @staticmethod
    def stochastic_rsi(prices: List[float], rsi_period: int = 14, stoch_period: int = 14) -> Optional[Dict[str, float]]:
        """
        Stochastic RSI - RSI of RSI for more sensitive overbought/oversold signals.
        Returns %K (0-100) and smoothed %D.
        """
        if len(prices) < rsi_period + stoch_period + 1:
            return None

        rsi_values = []
        for i in range(rsi_period + 1, len(prices) + 1):
            r = TechnicalIndicators.rsi(prices[:i], rsi_period)
            if r is not None:
                rsi_values.append(r)

        if len(rsi_values) < stoch_period:
            return None

        recent = rsi_values[-stoch_period:]
        lowest = min(recent)
        highest = max(recent)
        rng = highest - lowest

        k = ((rsi_values[-1] - lowest) / rng * 100) if rng > 0 else 50.0
        d = sum(rsi_values[-3:]) / 3 if len(rsi_values) >= 3 else k
        d = ((d - lowest) / rng * 100) if rng > 0 else 50.0

        return {"k": round(k, 2), "d": round(d, 2)}

    @staticmethod
    def volume_profile(candles: List[Dict], period: int = 20) -> Optional[Dict[str, float]]:
        """
        Volume analysis: ratio of current volume to average, and up/down volume ratio.
        """
        if len(candles) < period:
            return None

        recent = candles[-period:]
        volumes = [c["volume"] for c in recent]
        avg_vol = sum(volumes) / len(volumes) if volumes else 1

        current_vol = candles[-1]["volume"]
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

        up_vol = sum(c["volume"] for c in recent if c["close"] >= c["open"])
        down_vol = sum(c["volume"] for c in recent if c["close"] < c["open"])
        total_vol = up_vol + down_vol
        up_down_ratio = up_vol / down_vol if down_vol > 0 else 2.0

        return {
            "vol_ratio": round(vol_ratio, 2),
            "up_down_ratio": round(up_down_ratio, 2),
            "avg_volume": round(avg_vol, 0),
            "current_volume": current_vol,
        }

    @staticmethod
    def candlestick_patterns(candles: List[Dict]) -> Optional[Dict]:
        """
        Detect candlestick formations on the last few bars.
        Returns a dict with pattern name, direction bias (-1 to +1), and strength.

        Patterns detected:
        - Engulfing (bullish/bearish)
        - Hammer / Inverted Hammer
        - Doji (indecision)
        - Morning Star / Evening Star (3-bar reversal)
        - Three White Soldiers / Three Black Crows (3-bar continuation)
        """
        if len(candles) < 3:
            return None

        patterns = []

        c0 = candles[-3]  # oldest of last 3
        c1 = candles[-2]  # middle
        c2 = candles[-1]  # most recent

        body2 = c2["close"] - c2["open"]
        body1 = c1["close"] - c1["open"]
        body0 = c0["close"] - c0["open"]
        range2 = c2["high"] - c2["low"] or 0.0001
        range1 = c1["high"] - c1["low"] or 0.0001
        abs_body2 = abs(body2)
        abs_body1 = abs(body1)
        abs_body0 = abs(body0)

        # --- Engulfing ---
        # Bullish: previous bearish, current bullish body engulfs previous body
        if body1 < 0 and body2 > 0 and c2["open"] <= c1["close"] and c2["close"] >= c1["open"]:
            patterns.append({"name": "BULLISH_ENGULFING", "bias": 0.7, "strength": abs_body2 / range2})
        # Bearish: previous bullish, current bearish body engulfs previous body
        if body1 > 0 and body2 < 0 and c2["open"] >= c1["close"] and c2["close"] <= c1["open"]:
            patterns.append({"name": "BEARISH_ENGULFING", "bias": -0.7, "strength": abs_body2 / range2})

        # --- Hammer / Inverted Hammer ---
        lower_wick2 = min(c2["open"], c2["close"]) - c2["low"]
        upper_wick2 = c2["high"] - max(c2["open"], c2["close"])
        # Hammer: small body at top, long lower wick (>2x body), short upper wick
        if abs_body2 > 0 and lower_wick2 >= abs_body2 * 2 and upper_wick2 < abs_body2 * 0.5:
            patterns.append({"name": "HAMMER", "bias": 0.6, "strength": lower_wick2 / range2})
        # Inverted Hammer / Shooting Star: small body at bottom, long upper wick
        if abs_body2 > 0 and upper_wick2 >= abs_body2 * 2 and lower_wick2 < abs_body2 * 0.5:
            # Shooting star if after uptrend (bearish), inverted hammer if after downtrend (bullish)
            if c1["close"] > c0["close"]:  # after uptick = shooting star
                patterns.append({"name": "SHOOTING_STAR", "bias": -0.6, "strength": upper_wick2 / range2})
            else:
                patterns.append({"name": "INVERTED_HAMMER", "bias": 0.5, "strength": upper_wick2 / range2})

        # --- Doji ---
        # Very small body relative to range (<10%)
        if range2 > 0 and abs_body2 / range2 < 0.10:
            patterns.append({"name": "DOJI", "bias": 0.0, "strength": 1.0 - abs_body2 / range2})

        # --- Morning Star (bullish 3-bar reversal) ---
        # Bar 0: large bearish, Bar 1: small body (star), Bar 2: large bullish closing above bar0 midpoint
        mid0 = (c0["open"] + c0["close"]) / 2
        if body0 < 0 and abs_body0 > range2 * 0.3 and abs_body1 < abs_body0 * 0.4 and body2 > 0 and c2["close"] > mid0:
            patterns.append({"name": "MORNING_STAR", "bias": 0.8, "strength": abs_body2 / range2})

        # --- Evening Star (bearish 3-bar reversal) ---
        if body0 > 0 and abs_body0 > range2 * 0.3 and abs_body1 < abs_body0 * 0.4 and body2 < 0 and c2["close"] < mid0:
            patterns.append({"name": "EVENING_STAR", "bias": -0.8, "strength": abs_body2 / range2})

        # --- Three White Soldiers (bullish continuation) ---
        if body0 > 0 and body1 > 0 and body2 > 0:
            if c1["close"] > c0["close"] and c2["close"] > c1["close"]:
                if c1["open"] > c0["open"] and c2["open"] > c1["open"]:
                    patterns.append({"name": "THREE_WHITE_SOLDIERS", "bias": 0.7, "strength": 0.8})

        # --- Three Black Crows (bearish continuation) ---
        if body0 < 0 and body1 < 0 and body2 < 0:
            if c1["close"] < c0["close"] and c2["close"] < c1["close"]:
                if c1["open"] < c0["open"] and c2["open"] < c1["open"]:
                    patterns.append({"name": "THREE_BLACK_CROWS", "bias": -0.7, "strength": 0.8})

        if not patterns:
            return {"patterns": [], "net_bias": 0.0}

        # Net bias: weighted average by strength
        total_strength = sum(p["strength"] for p in patterns)
        net_bias = sum(p["bias"] * p["strength"] for p in patterns) / total_strength if total_strength > 0 else 0

        return {
            "patterns": patterns,
            "net_bias": round(max(-1, min(1, net_bias)), 4),
        }

    @staticmethod
    def calculate_all(candles: List[Dict], period: int = 14) -> Optional[Dict]:
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
            "adx": TechnicalIndicators.adx(highs, lows, closes, 14),
            "stoch_rsi": TechnicalIndicators.stochastic_rsi(closes, 14, 14),
            "volume_profile": TechnicalIndicators.volume_profile(candles, 20),
            "candlestick_patterns": TechnicalIndicators.candlestick_patterns(candles),
        }
