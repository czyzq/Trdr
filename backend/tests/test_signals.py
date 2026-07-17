"""
Tests for signal model validation.

Run: python -m pytest tests/test_signals.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import SignalDirection


class TestSignalValidation:
    """Test Pydantic model validation for signals."""

    def test_signal_score_range_valid(self):
        """Test signal with valid score range."""
        from models import Signal

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
        """Test signal with score above 1.0 - should be rejected."""
        from models import Signal
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
        from models import Signal
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
        from models import Signal
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
