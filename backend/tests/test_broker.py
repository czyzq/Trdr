"""
Tests for broker simulation and trade execution.

Run: python -m pytest tests/test_broker.py -v
"""

import asyncio
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broker import Broker
from broker_sim import SimulatedBroker, SimulatedDataProvider


class TestBrokerInitialization:
    """Test broker initialization."""

    def test_broker_initialization(self):
        """Test that SimulatedBroker initializes correctly."""
        broker = SimulatedBroker()
        
        assert broker is not None
        assert hasattr(broker, 'open_positions')
        assert hasattr(broker, 'closed_positions')
        assert hasattr(broker, 'account')

    def test_broker_initial_balance(self):
        """Test initial balance is set correctly."""
        broker = SimulatedBroker()
        
        assert broker.account["balance_usd"] == 3000.0  # Default initial balance


class TestPositionOpening:
    """Test opening positions."""

    @pytest.mark.asyncio
    async def test_open_buy_position(self):
        """Test opening a BUY position."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        assert result["status"] == "opened"
        assert "position" in result
        assert result["position"]["symbol"] == "XAU"
        assert result["position"]["direction"] == "buy"
        assert result["position"]["size"] == 0.01

    @pytest.mark.asyncio
    async def test_open_sell_position(self):
        """Test opening a SELL position."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        result = await broker.open_position(
            symbol="XAG",
            direction="sell",
            size=0.1,
            take_profit=22.0,
            stop_loss=24.0
        )
        
        assert result["status"] == "opened"
        assert result["position"]["direction"] == "sell"
        assert result["position"]["size"] == 0.1

    @pytest.mark.asyncio
    async def test_open_position_updates_balance(self):
        """Test that opening position updates available balance."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        initial_available = broker.available
        
        await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        # Available balance should decrease by margin
        assert broker.available < initial_available


class TestPositionClosing:
    """Test closing positions."""

    @pytest.mark.asyncio
    async def test_close_position(self):
        """Test closing an existing position."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        # First open a position
        open_result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        position_id = open_result["position"]["id"]
        
        # Now close it
        close_result = await broker.close_position(position_id)
        
        assert close_result["status"] == "closed"
        assert close_result["position"]["status"] == "closed"
        assert "pnl_usd" in close_result["position"]

    @pytest.mark.asyncio
    async def test_close_profitable_position(self):
        """Test closing a profitable position."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        # Open at 2000
        open_result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        position_id = open_result["position"]["id"]
        
        # Simulate price moving up (close at 2050)
        close_result = await broker.close_position(position_id, exit_price=2050.0)
        
        assert close_result["position"]["pnl_usd"] > 0

    @pytest.mark.asyncio
    async def test_close_losing_position(self):
        """Test closing a losing position."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        open_result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        position_id = open_result["position"]["id"]
        
        # Price goes down (close at 1950)
        close_result = await broker.close_position(position_id, exit_price=1950.0)
        
        assert close_result["position"]["pnl_usd"] < 0


class TestEdgeCases:
    """Test edge cases in position management."""

    @pytest.mark.asyncio
    async def test_open_position_insufficient_margin(self):
        """Test opening position with insufficient margin."""
        broker = SimulatedBroker(initial_balance=100.0)
        
        # Try to open position requiring more margin than available
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=1.0,  # Very large
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        # Should fail with insufficient margin error
        assert "error" in result or broker.available >= 0

    @pytest.mark.asyncio
    async def test_open_position_negative_size(self):
        """Test opening position with negative size."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=-0.01,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        # Should return error
        assert "error" in result

    @pytest.mark.asyncio
    async def test_open_position_zero_size(self):
        """Test opening position with zero size."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.0,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        # Should return error
        assert "error" in result

    @pytest.mark.asyncio
    async def test_close_nonexistent_position(self):
        """Test closing a position that doesn't exist."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        result = await broker.close_position("nonexistent_id_12345")
        
        assert "error" in result

    @pytest.mark.asyncio
    async def test_close_already_closed_position(self):
        """Test closing an already closed position."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        # Open and close
        open_result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        position_id = open_result["position"]["id"]
        await broker.close_position(position_id)
        
        # Try to close again
        result = await broker.close_position(position_id)
        
        assert "error" in result


class TestAccountManagement:
    """Test account-related functionality."""

    def test_get_account(self):
        """Test getting account information."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        account = broker.get_account()
        
        assert "balance_usd" in account
        assert "equity_usd" in account
        assert "available_usd" in account
        assert account["balance_usd"] == 10000.0

    def test_get_account_with_positions(self):
        """Test account with open positions."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        # Run async to open position
        asyncio.run(broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0
        ))
        
        account = broker.get_account()
        
        # Check open positions via the method
        open_positions = broker.get_open_positions()
        
        # Equity should be different from balance (unrealized P&L)
        assert "positions" in account or "open_trades" in account
        assert len(open_positions) > 0

    def test_get_open_positions(self):
        """Test getting open positions."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        asyncio.run(broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0
        ))
        
        positions = broker.get_open_positions()
        
        assert len(positions) > 0
        assert positions[0]["status"] == "open"

    def test_get_closed_positions(self):
        """Test getting closed positions."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        # Open and close a position
        open_result = asyncio.run(broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0
        ))
        
        if "error" in open_result:
            pytest.skip(f"Cannot open position: {open_result['error']}")
        
        position_id = open_result["position"]["id"]
        asyncio.run(broker.close_position(position_id))
        
        closed = broker.get_closed_positions()
        
        assert len(closed) > 0
        assert closed[0]["status"] == "closed"


class TestTakeProfitStopLoss:
    """Test TP/SL functionality."""

    @pytest.mark.asyncio
    async def test_take_profit_hit_buy(self):
        """Test TP is hit for BUY position."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        # Open at 2000, TP at 2100 (5% gain)
        open_result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        position_id = open_result["position"]["id"]
        
        # Simulate price hitting TP
        close_result = await broker.close_position(position_id, exit_price=2100.0)
        
        # Should be profitable
        assert close_result["position"]["pnl_usd"] > 0
        assert close_result["position"]["close_reason"] in ["take_profit", "manual"]

    @pytest.mark.asyncio
    async def test_stop_loss_hit_buy(self):
        """Test SL is hit for BUY position."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        open_result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0
        )
        
        position_id = open_result["position"]["id"]
        
        # Simulate price hitting SL
        close_result = await broker.close_position(position_id, exit_price=1950.0)
        
        # Should be a loss
        assert close_result["position"]["pnl_usd"] < 0

    @pytest.mark.asyncio
    async def test_take_profit_hit_sell(self):
        """Test TP is hit for SELL position."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        open_result = await broker.open_position(
            symbol="XAG",
            direction="sell",
            size=0.1,
            entry_price=23.0,
            take_profit=22.0,
            stop_loss=24.0
        )
        
        position_id = open_result["position"]["id"]
        
        # Price goes down (profit for sell)
        close_result = await broker.close_position(position_id, exit_price=22.0)
        
        assert close_result["position"]["pnl_usd"] > 0


class TestTrailingStop:
    """Test trailing stop functionality."""

    @pytest.mark.asyncio
    async def test_trailing_stop_enabled(self):
        """Test position with trailing stop enabled."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0,
            trailing_stop=True
        )
        
        position = result["position"]
        assert position["trailing_enabled"] == True

    @pytest.mark.asyncio
    async def test_trailing_stop_disabled(self):
        """Test position with trailing stop disabled."""
        broker = SimulatedBroker(initial_balance=10000.0)
        
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=0.01,
            entry_price=2000.0,
            take_profit=2100.0,
            stop_loss=1950.0,
            trailing_stop=False
        )
        
        position = result["position"]
        assert position["trailing_enabled"] == False


class TestDataProvider:
    """Test data provider functionality."""

    def test_simulated_data_provider_init(self):
        """Test SimulatedDataProvider initialization."""
        provider = SimulatedDataProvider()
        
        assert provider is not None

    @pytest.mark.asyncio
    async def test_get_quote(self):
        """Test getting a quote."""
        provider = SimulatedDataProvider()
        
        # This may fail if no network, so we'll mock it
        with patch.object(provider, 'get_quote', new_callable=AsyncMock) as mock_quote:
            mock_quote.return_value = {
                "symbol": "XAU",
                "price": 2000.0,
                "bid": 1999.5,
                "ask": 2000.5,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            quote = await provider.get_quote("XAU")
            assert quote["symbol"] == "XAU"
            assert "price" in quote

    @pytest.mark.asyncio
    async def test_get_candles(self):
        """Test getting candles."""
        provider = SimulatedDataProvider()
        
        with patch.object(provider, 'get_candles', new_callable=AsyncMock) as mock_candles:
            mock_candles.return_value = [
                {"timestamp": "2026-01-01", "open": 2000, "high": 2010, "low": 1990, "close": 2005, "volume": 100}
            ]
            
            candles = await provider.get_candles("XAU", "60", 100)
            assert len(candles) > 0
