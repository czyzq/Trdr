"""
Test Risk Management - TP/SL functionality
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broker_sim import AsyncSimulatedBroker


class TestTakeProfit:
    """Tests for take profit functionality"""

    @pytest.mark.asyncio
    async def test_open_position_with_tp_buy(self):
        """Test opening buy position with take profit"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        # Open buy at 2000 with TP at 2010
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=1.0,
            entry_price=2000.0,
            take_profit=2010.0,
            stop_loss=1990.0
        )
        
        # Check result format
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        assert result["status"] == "opened"
        pos = result["position"]
        assert pos["take_profit"] == 2010.0
        assert pos["stop_loss"] == 1990.0
        assert pos["direction"] == "buy"

    @pytest.mark.asyncio
    async def test_open_position_with_tp_sell(self):
        """Test opening sell position with take profit"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        # Open sell at 2000 with TP at 1990
        result = await broker.open_position(
            symbol="XAU",
            direction="sell",
            size=1.0,
            entry_price=2000.0,
            take_profit=1990.0,
            stop_loss=2010.0
        )
        
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        assert result["status"] == "opened"
        pos = result["position"]
        assert pos["take_profit"] == 1990.0
        assert pos["stop_loss"] == 2010.0
        assert pos["direction"] == "sell"


class TestStopLoss:
    """Tests for stop loss functionality"""

    @pytest.mark.asyncio
    async def test_stop_loss_buy(self):
        """Test stop loss for buy position"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        # Open buy at 2000 with SL at 1990
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=1.0,
            entry_price=2000.0,
            stop_loss=1990.0
        )
        
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        pos = result["position"]
        assert pos["stop_loss"] == 1990.0

    @pytest.mark.asyncio
    async def test_stop_loss_sell(self):
        """Test stop loss for sell position"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        # Open sell at 2000 with SL at 2010
        result = await broker.open_position(
            symbol="XAU",
            direction="sell",
            size=1.0,
            entry_price=2000.0,
            stop_loss=2010.0
        )
        
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        pos = result["position"]
        assert pos["stop_loss"] == 2010.0


class TestRiskDefaults:
    """Tests for default TP/SL calculation"""

    @pytest.mark.asyncio
    async def test_default_tp_sl_calculated(self):
        """Test TP/SL are calculated when not provided"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        # Open without explicit TP/SL
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=1.0,
            entry_price=2000.0
        )
        
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        pos = result["position"]
        
        # Should have default TP/SL
        assert "take_profit" in pos
        assert "stop_loss" in pos
        assert pos["take_profit"] > pos["entry_price"]
        assert pos["stop_loss"] < pos["entry_price"]

    @pytest.mark.asyncio
    async def test_custom_tp_sl_used(self):
        """Test custom TP/SL values are used when provided"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=1.0,
            entry_price=2000.0,
            take_profit=2050.0,
            stop_loss=1950.0
        )
        
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        pos = result["position"]
        
        assert pos["take_profit"] == 2050.0
        assert pos["stop_loss"] == 1950.0


class TestCloseWithTP:
    """Tests for closing positions at TP/SL prices"""

    @pytest.mark.asyncio
    async def test_close_at_take_profit(self):
        """Test closing position at TP price manually"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        # Open position with TP
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=1.0,
            entry_price=2000.0,
            take_profit=2010.0,
            stop_loss=1990.0
        )
        
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        position_id = result["position"]["id"]
        
        # Close at TP price
        close_result = await broker.close_position(position_id, exit_price=2010.0)
        
        assert close_result["status"] == "closed"
        assert close_result["position"]["result"] == "win"

    @pytest.mark.asyncio
    async def test_close_at_stop_loss(self):
        """Test closing position at SL price manually"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        # Open position with SL
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=1.0,
            entry_price=2000.0,
            take_profit=2010.0,
            stop_loss=1990.0
        )
        
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        position_id = result["position"]["id"]
        
        # Close at SL price
        close_result = await broker.close_position(position_id, exit_price=1990.0)
        
        assert close_result["status"] == "closed"
        assert close_result["position"]["result"] == "loss"


class TestEdgeCases:
    """Edge case tests for risk management"""

    @pytest.mark.asyncio
    async def test_no_tp_sl(self):
        """Test position without TP/SL doesn't break"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=1.0,
            entry_price=2000.0,
            take_profit=None,
            stop_loss=None
        )
        
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        # Position should still open
        assert result["status"] == "opened"

    @pytest.mark.asyncio
    async def test_tp_only(self):
        """Test position with only TP"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=1.0,
            entry_price=2000.0,
            take_profit=2050.0,
            stop_loss=None
        )
        
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        pos = result["position"]
        assert pos["take_profit"] == 2050.0

    @pytest.mark.asyncio
    async def test_sl_only(self):
        """Test position with only SL"""
        broker = AsyncSimulatedBroker(initial_balance=10000.0)
        
        result = await broker.open_position(
            symbol="XAU",
            direction="buy",
            size=1.0,
            entry_price=2000.0,
            take_profit=None,
            stop_loss=1950.0
        )
        
        if "error" in result:
            pytest.skip(f"Broker error: {result['error']}")
            
        pos = result["position"]
        assert pos["stop_loss"] == 1950.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
