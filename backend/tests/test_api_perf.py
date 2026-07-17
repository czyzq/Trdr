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


class TestSampleDataPerformance:
    """Test sample data generation performance."""

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


# ── Regression Tests ──


class TestRegression:
    """Regression tests for known bugs."""

    def test_empty_candles_handling(self):
        """Test handling of empty candle lists."""
        from indicators import TechnicalIndicators

        # Test with empty price list
        result = TechnicalIndicators.rsi([], period=14)
        assert result is None  # Should return None for empty input
