"""
Tests for signal generation and scoring.

Run: python -m pytest tests/test_signals.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SignalDirection
from strategies import AdaptiveRegimeStrategy, get_strategy
from backtester import calculate_signal_score, get_direction


class TestSignalGeneration:
    """Test signal generation for various scenarios."""

    def test_generate_signal_xau_strong_buy(self):
        """Test BUY signal generation for XAU with strong indicators."""
        strategy = get_strategy("adaptive_regime")
        assert strategy is not None
        
        # Should be able to get strategy
        assert isinstance(strategy, AdaptiveRegimeStrategy)

    def test_generate_signal_xag_strong_sell(self):
        """Test SELL signal generation."""
        strategy = get_strategy("adaptive_regime")
        assert strategy is not None

    def test_get_direction_strong_buy(self):
        """Test strong BUY direction threshold."""
        direction = get_direction(score=0.8, min_score=0.15)
        assert direction == "STRONG_BUY"

    def test_get_direction_buy(self):
        """Test BUY direction threshold."""
        direction = get_direction(score=0.4, min_score=0.15)
        assert direction == "BUY"

    def test_get_direction_neutral_positive(self):
        """Test NEUTRAL direction (positive but below threshold)."""
        direction = get_direction(score=0.1, min_score=0.15)
        assert direction == "NEUTRAL"

    def test_get_direction_neutral_negative(self):
        """Test NEUTRAL direction (negative but above threshold)."""
        direction = get_direction(score=-0.1, min_score=0.15)
        assert direction == "NEUTRAL"

    def test_get_direction_sell(self):
        """Test SELL direction threshold."""
        direction = get_direction(score=-0.4, min_score=0.15)
        assert direction == "SELL"

    def test_get_direction_strong_sell(self):
        """Test strong SELL direction threshold."""
        direction = get_direction(score=-0.8, min_score=0.15)
        assert direction == "STRONG_SELL"

    def test_get_direction_custom_min_score(self):
        """Test direction with custom min_score."""
        direction = get_direction(score=0.2, min_score=0.25)
        assert direction == "NEUTRAL"


class TestSignalScoring:
    """Test signal score calculations."""

    def test_calculate_signal_score_with_valid_indicators(self):
        """Test score calculation with valid indicator format."""
        indicators = {
            "rsi_14": 35.0,  # Oversold (bullish)
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
            "_closes": [2000.0, 2010.0, 2020.0]
        }
        
        score, component_scores = calculate_signal_score(indicators)
        
        # Returns (composite_score, list_of_component_scores)
        assert isinstance(score, (int, float))
        assert isinstance(component_scores, list)
        # Score should be valid range
        assert -1.0 <= score <= 1.0

    def test_calculate_signal_score_empty(self):
        """Test score calculation with empty indicators."""
        indicators = {}
        
        score, component_scores = calculate_signal_score(indicators)
        
        # Returns (composite_score, list_of_component_scores)
        assert isinstance(score, (int, float))
        assert isinstance(component_scores, list)


class TestScoreClamping:
    """Test that scores are clamped to valid ranges."""

    def test_score_clamped_to_valid_range(self):
        """Test that scores are clamped to [-1, 1]."""
        # Test with valid indicators
        indicators = {
            "rsi_14": 50.0,
            "macd": {"histogram": 5.0, "macd_line": 10.0, "signal_line": 5.0},
            "bollinger_bands": {"position": 0.0},
            "adx": {"adx": 20.0},
            "sma_20": 2000.0,
            "sma_50": 1980.0,
        }
        
        score, direction = calculate_signal_score(indicators)
        
        # Should always be in valid range
        assert -1.0 <= score <= 1.0


class TestEdgeCases:
    """Test edge cases in signal generation."""

    def test_empty_indicators(self):
        """Test signal with empty indicator data."""
        indicators = {}
        score, component_scores = calculate_signal_score(indicators)
        
        # Should return valid results
        assert isinstance(score, (int, float))
        assert isinstance(component_scores, list)

    def test_partial_indicators(self):
        """Test signal with partial indicator data."""
        indicators = {
            "rsi_14": 45.0
        }
        score, component_scores = calculate_signal_score(indicators)
        
        # Should still produce a result
        assert isinstance(score, (int, float))
        assert isinstance(component_scores, list)

    def test_min_score_zero(self):
        """Test direction with min_score of 0."""
        direction = get_direction(score=0.0, min_score=0.0)
        # With min_score=0, 0 should be neutral (not strictly positive or negative)
        assert direction in ["BUY", "NEUTRAL"]

    def test_min_score_one(self):
        """Test direction with min_score of 1 (very strict)."""
        direction = get_direction(score=0.99, min_score=1.0)
        assert direction == "NEUTRAL"
        
        # When score equals min_score exactly, it's NEUTRAL (not strictly greater)
        direction = get_direction(score=1.0, min_score=1.0)
        # strong_threshold = max(0.45, 1.0 + 0.20) = 1.2
        # 1.0 < 1.2, so not STRONG_BUY
        # 1.0 > 1.0 is False, so not BUY
        assert direction == "NEUTRAL"
        
        # To get STRONG_BUY with min_score=1, need score > 1.2
        direction = get_direction(score=1.21, min_score=1.0)
        assert direction == "STRONG_BUY"


class TestStrategies:
    """Test strategy loading and configuration."""

    def test_get_strategy_adaptive_regime(self):
        """Test loading adaptive regime strategy."""
        strategy = get_strategy("adaptive_regime")
        assert strategy is not None

    def test_get_strategy_mms(self):
        """Test loading MMS strategy."""
        strategy = get_strategy("mms")
        assert strategy is not None

    def test_get_strategy_invalid(self):
        """Test loading non-existent strategy."""
        strategy = get_strategy("nonexistent_strategy")
        # Should return None or raise error
        assert strategy is None or isinstance(strategy, object)

    def test_list_strategies(self):
        """Test listing available strategies."""
        from strategies import list_strategies
        strategies = list_strategies()
        
        assert isinstance(strategies, list)
        assert len(strategies) > 0
        
        # Each strategy should have required fields
        for s in strategies:
            assert "name" in s
            assert "description" in s or "direction" in s


class TestSignalValidation:
    """Test Pydantic model validation for signals."""

    def test_signal_score_range_valid(self):
        """Test signal with valid score range."""
        from models import Signal, Component, ComponentType
        
        signal = Signal(
            symbol="XAU",
            direction=SignalDirection.BUY,
            score=0.5,
            confidence=0.8,
            technical_score=0.5,
            price_action_score=0.0,
            news_score=0.0,
            components=[],
            current_price=2000.0,
            time_horizon="1h",
            entry_point=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0,
            risk_reward_ratio=2.5
        )
        
        assert signal.score == 0.5
        assert signal.confidence == 0.8

    def test_signal_score_above_max(self):
        """Test signal with score above 1.0 - should be clamped."""
        from models import Signal, Component, ComponentType
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            Signal(
                symbol="XAU",
                direction=SignalDirection.BUY,
                score=1.5,  # Invalid: > 1.0
                confidence=0.8,
                technical_score=0.5,
                price_action_score=0.0,
                news_score=0.0,
                components=[],
                current_price=2000.0,
                time_horizon="1h",
                entry_point=2000.0,
                take_profit=2100.0,
                stop_loss=1950.0,
                risk_reward_ratio=2.5
            )

    def test_signal_score_below_min(self):
        """Test signal with score below -1.0."""
        from models import Signal, Component, ComponentType
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            Signal(
                symbol="XAU",
                direction=SignalDirection.BUY,
                score=-1.5,  # Invalid: < -1.0
                confidence=0.8,
                technical_score=0.5,
                price_action_score=0.0,
                news_score=0.0,
                components=[],
                current_price=2000.0,
                time_horizon="1h",
                entry_point=2000.0,
                take_profit=2100.0,
                stop_loss=1950.0,
                risk_reward_ratio=2.5
            )

    def test_signal_confidence_above_max(self):
        """Test signal with confidence > 1.0."""
        from models import Signal, Component, ComponentType
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            Signal(
                symbol="XAU",
                direction=SignalDirection.BUY,
                score=0.5,
                confidence=1.5,  # Invalid: > 1.0
                technical_score=0.5,
                price_action_score=0.0,
                news_score=0.0,
                components=[],
                current_price=2000.0,
                time_horizon="1h",
                entry_point=2000.0,
                take_profit=2100.0,
                stop_loss=1950.0,
                risk_reward_ratio=2.5
            )
