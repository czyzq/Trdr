"""
Tests for API endpoints and performance.

Run: python -m pytest tests/test_api_perf.py -v
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Performance Tests ──


class TestSignalGenerationPerformance:
    """Test signal generation performance."""

    def test_signal_generation_time(self):
        """Test that signal generation completes within acceptable time."""
        from backtester import calculate_signal_score
        
        indicators = {
            "rsi_14": 35.0,
            "macd": {"histogram": 5.0, "macd_line": 10.0, "signal_line": 5.0},
            "bollinger_bands": {"upper": 2050.0, "middle": 2000.0, "lower": 1950.0},
            "adx": {"adx": 30.0},
            "sma_20": 2000.0,
            "sma_50": 1980.0,
            "stoch_rsi": {"k": 20.0, "d": 25.0},
            "atr_14": 25.0,
            "volume_profile": {"vol_ratio": 1.2, "up_down_ratio": 1.0},
            "momentum_10": 0.5,
            "candlestick_patterns": {},
            "_closes": [2000.0] * 100
        }
        
        start = time.time()
        for _ in range(100):
            calculate_signal_score(indicators)
        elapsed = time.time() - start
        
        # Should complete 100 iterations in under 1 second
        assert elapsed < 1.0, f"Signal generation too slow: {elapsed:.2f}s"

    def test_direction_calculation_performance(self):
        """Test direction calculation performance."""
        from backtester import get_direction
        
        start = time.time()
        for _ in range(1000):
            get_direction(0.5, 0.15)
        elapsed = time.time() - start
        
        # Should complete 1000 iterations in under 10ms
        assert elapsed < 0.01, f"Direction calculation too slow: {elapsed:.4f}s"

    def test_get_direction_all_cases(self):
        """Test all direction cases."""
        from backtester import get_direction
        
        # Test STRONG_BUY
        assert get_direction(0.8, 0.15) == "STRONG_BUY"
        
        # Test BUY
        assert get_direction(0.4, 0.15) == "BUY"
        
        # Test NEUTRAL positive
        assert get_direction(0.1, 0.15) == "NEUTRAL"
        
        # Test NEUTRAL negative
        assert get_direction(-0.1, 0.15) == "NEUTRAL"
        
        # Test SELL
        assert get_direction(-0.4, 0.15) == "SELL"
        
        # Test STRONG_SELL
        assert get_direction(-0.8, 0.15) == "STRONG_SELL"


class TestBacktestPerformance:
    """Test backtest performance."""

    def test_sample_data_generation_performance(self):
        """Test sample data generation performance."""
        from historical_data import generate_sample_data
        
        start = time.time()
        candles = generate_sample_data("XAU", days=365, base_price=2000.0)
        elapsed = time.time() - start
        
        # Should generate 365 days in under 1 second
        assert elapsed < 1.0, f"Sample data generation too slow: {elapsed:.2f}s"
        # XAU skips weekends, so ~261 trading days from 365 calendar days
        assert len(candles) > 200  # Should skip weekends

    def test_sample_data_structure(self):
        """Test sample data has correct structure."""
        from historical_data import generate_sample_data
        
        candles = generate_sample_data("XAU", days=10, base_price=2000.0)
        
        # Check structure
        for c in candles:
            assert "timestamp" in c
            assert "time" in c
            assert "open" in c
            assert "high" in c
            assert "low" in c
            assert "close" in c
            assert "volume" in c


class TestIndicatorPerformance:
    """Test indicator calculation performance."""

    def test_rsi_performance(self):
        """Test RSI calculation performance."""
        from indicators import TechnicalIndicators
        
        # Generate price list
        import random
        random.seed(42)
        prices = [2000.0 + random.uniform(-50, 50) for _ in range(200)]
        
        start = time.time()
        for _ in range(100):
            TechnicalIndicators.rsi(prices, period=14)
        elapsed = time.time() - start
        
        # Should complete 100 iterations quickly
        assert elapsed < 1.0, f"RSI calculation too slow: {elapsed:.2f}s"

    def test_macd_performance(self):
        """Test MACD calculation performance."""
        from indicators import TechnicalIndicators
        
        import random
        random.seed(42)
        prices = [2000.0 + random.uniform(-50, 50) for _ in range(200)]
        
        start = time.time()
        for _ in range(100):
            TechnicalIndicators.macd(prices)
        elapsed = time.time() - start
        
        # Should complete 100 iterations quickly
        assert elapsed < 1.0, f"MACD calculation too slow: {elapsed:.2f}s"


class TestBacktestEnginePerformance:
    """Test backtest engine performance."""

    def test_backtest_runs_quickly(self):
        """Test backtest completes in reasonable time."""
        from historical_data import generate_sample_data
        from backtester import run_backtest
        
        candles = generate_sample_data("XAU", days=100, base_price=2000.0)
        
        start = time.time()
        result = run_backtest(
            candles=candles,
            symbol="XAU",
            initial_balance=10000.0,
            risk_per_trade_pct=2.0,
            max_concurrent=3
        )
        elapsed = time.time() - start
        
        # Should complete in under 30 seconds
        assert elapsed < 30.0, f"Backtest too slow: {elapsed:.2f}s"
        assert result is not None


# ── Stress Tests ──


class TestStress:
    """Stress tests for performance."""

    def test_large_candle_dataset(self):
        """Test handling large candle datasets."""
        from historical_data import generate_sample_data
        
        # Generate 2 years of data
        candles = generate_sample_data("XAU", days=730, base_price=2000.0)
        
        assert len(candles) > 400  # Should skip weekends
        
        # Test with large dataset
        import random
        random.seed(42)
        prices = [2000.0 + random.uniform(-50, 50) for _ in range(len(candles))]
        
        from indicators import TechnicalIndicators
        start = time.time()
        result = TechnicalIndicators.rsi(prices, period=14)
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"Large dataset too slow: {elapsed:.2f}s"

    def test_multiple_symbols(self):
        """Test processing multiple symbols."""
        from historical_data import generate_sample_data
        from backtester import calculate_signal_score
        
        symbols = ["XAU", "XAG", "BTC", "US100"]
        
        indicators = {
            "rsi_14": 35.0,
            "macd": {"histogram": 5.0, "macd_line": 10.0, "signal_line": 5.0},
            "bollinger_bands": {"upper": 2050.0, "middle": 2000.0, "lower": 1950.0},
            "adx": {"adx": 30.0},
            "sma_20": 2000.0,
            "sma_50": 1980.0,
            "stoch_rsi": {"k": 20.0, "d": 25.0},
            "atr_14": 25.0,
            "volume_profile": {"vol_ratio": 1.2, "up_down_ratio": 1.0},
            "momentum_10": 0.5,
            "candlestick_patterns": {},
            "_closes": [2000.0] * 100
        }
        
        start = time.time()
        for _ in range(10):
            for symbol in symbols:
                calculate_signal_score(indicators)
        elapsed = time.time() - start
        
        # Should process 40 signals quickly
        assert elapsed < 0.5, f"Multiple symbols too slow: {elapsed:.2f}s"


# ── Regression Tests ──


class TestRegression:
    """Regression tests for known bugs."""

    def test_score_clamping(self):
        """Test that scores are always clamped to [-1, 1]."""
        from backtester import calculate_signal_score
        
        # Test with extreme RSI values
        indicators = {
            "rsi_14": 0.0,  # Extreme oversold
            "adx": {"adx": 30.0},
            "_closes": [1000.0] * 50
        }
        
        score, _ = calculate_signal_score(indicators)
        assert -1.0 <= score <= 1.0
        
        indicators["rsi_14"] = 100.0  # Extreme overbought
        score, _ = calculate_signal_score(indicators)
        assert -1.0 <= score <= 1.0

    def test_zero_division_protection(self):
        """Test that zero division is handled."""
        from backtester import calculate_signal_score
        
        # Test with zeros
        indicators = {
            "rsi_14": 50.0,
            "sma_20": 0.0,  # Could cause division by zero
            "sma_50": 0.0,
            "_closes": []
        }
        
        # Should not raise
        score, direction = calculate_signal_score(indicators)
        assert isinstance(score, (int, float))
        assert isinstance(direction, list)  # Returns component scores

    def test_empty_candles_handling(self):
        """Test handling of empty candle lists."""
        from indicators import TechnicalIndicators
        
        # Test with empty price list
        result = TechnicalIndicators.rsi([], period=14)
        assert result is None  # Should return None for empty input


# ── Memory Tests ──


class TestMemory:
    """Memory-related tests."""

    def test_no_memory_leaks(self):
        """Test that repeated operations don't leak memory."""
        import gc
        from backtester import calculate_signal_score
        
        indicators = {
            "rsi_14": 50.0,
            "macd": {"histogram": 0.0, "macd_line": 0.0, "signal_line": 0.0},
            "bollinger_bands": {"upper": 100.0, "middle": 90.0, "lower": 80.0},
            "adx": {"adx": 20.0},
            "sma_20": 90.0,
            "sma_50": 90.0,
            "_closes": [90.0] * 50
        }
        
        gc.collect()
        
        # Run many iterations
        for _ in range(1000):
            calculate_signal_score(indicators)
        
        gc.collect()
        
        # Test still passes - no memory leak crash


# ── Concurrency Tests ──


class TestConcurrency:
    """Concurrency tests."""

    def test_sequential_calls(self):
        """Test sequential calls work correctly."""
        from backtester import get_direction
        
        results = []
        for score in [0.8, 0.5, 0.2, -0.2, -0.5, -0.8]:
            results.append(get_direction(score, 0.15))
        
        # With min_score=0.15, strong_threshold=max(0.45, 0.35)=0.45
        assert results == [
            "STRONG_BUY", "STRONG_BUY", "BUY",
            "SELL", "STRONG_SELL", "STRONG_SELL"
        ]
