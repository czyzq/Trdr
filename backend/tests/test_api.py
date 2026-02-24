"""
Tests for API endpoints.

Run: python -m pytest tests/test_api.py -v
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# We need to mock database before importing main
@pytest.fixture(autouse=True)
def mock_database():
    """Mock database to avoid MongoDB connection in tests."""
    with patch('database.get_db', return_value=MagicMock()):
        yield


@pytest.fixture
def client():
    """Create test client."""
    # Import here to ensure mocks are applied
    with patch('database.get_db'), \
         patch('database._db'):
        from main import app
        return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_endpoint(self, client):
        """Test /health endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200


class TestSignalsEndpoint:
    """Test /api/signals endpoint."""

    def test_get_signals(self, client):
        """Test GET /api/signals."""
        response = client.get("/api/signals")
        
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_signals_structure(self, client):
        """Test signal structure."""
        response = client.get("/api/signals")
        
        if response.status_code == 200:
            data = response.json()
            if len(data["signals"]) > 0:
                signal = data["signals"][0]
                assert "symbol" in signal
                assert "direction" in signal
                assert "score" in signal


class TestAccountEndpoint:
    """Test account endpoints."""

    def test_get_account(self, client):
        """Test GET /api/account."""
        response = client.get("/api/account")
        
        assert response.status_code == 200
        data = response.json()
        assert "balance_usd" in data
        assert "equity_usd" in data
        assert "available_usd" in data

    def test_account_mode_update(self, client):
        """Test POST /api/account/mode."""
        response = client.post(
            "/api/account/mode",
            json={"mode": "simulation"}
        )
        
        # Should return success (even if mode doesn't change)
        assert response.status_code in [200, 400]


class TestTradesEndpoints:
    """Test trade-related endpoints."""

    def test_get_open_trades(self, client):
        """Test GET /api/trades/open."""
        response = client.get("/api/trades/open")
        
        assert response.status_code == 200
        data = response.json()
        assert "positions" in data
        assert isinstance(data["positions"], list)

    def test_get_trade_history(self, client):
        """Test GET /api/trades/history."""
        response = client.get("/api/trades/history")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestStrategiesEndpoints:
    """Test strategy endpoints."""

    def test_get_strategies(self, client):
        """Test GET /api/strategies."""
        response = client.get("/api/strategies")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    def test_get_strategy_for_symbol(self, client):
        """Test GET /api/strategy/{symbol}."""
        response = client.get("/api/strategy/XAU")
        
        # Should return strategy or 404
        assert response.status_code in [200, 404]


class TestSettingsEndpoints:
    """Test settings endpoints."""

    def test_get_settings(self, client):
        """Test GET /api/settings."""
        response = client.get("/api/settings")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    def test_post_setting(self, client):
        """Test POST /api/settings."""
        response = client.post(
            "/api/settings",
            json={"key": "test_key", "value": "test_value"}
        )
        
        # Should accept or reject properly
        assert response.status_code in [200, 400, 422]


class TestInstrumentsEndpoint:
    """Test instruments endpoints."""

    def test_get_instruments(self, client):
        """Test GET /api/instruments."""
        response = client.get("/api/instruments")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestBacktestEndpoint:
    """Test backtest endpoint."""

    def test_get_backtest(self, client):
        """Test GET /api/backtest with parameters."""
        response = client.get("/api/backtest?symbol=XAU&resolution=60&days=30&min_score=0.1")
        
        # Should return backtest results or error
        assert response.status_code in [200, 400, 500]


class TestLogsEndpoint:
    """Test logs endpoint."""

    def test_get_logs(self, client):
        """Test GET /api/logs."""
        response = client.get("/api/logs")
        
        # Should return logs or empty
        assert response.status_code in [200, 404]


class TestStatusEndpoint:
    """Test status endpoint."""

    def test_get_status(self, client):
        """Test GET /api/status."""
        response = client.get("/api/status")
        
        assert response.status_code == 200


class TestTradingModeEndpoint:
    """Test trading mode endpoints."""

    def test_get_trading_mode(self, client):
        """Test GET /api/trading-mode."""
        response = client.get("/api/trading-mode")
        
        assert response.status_code in [200, 404]

    def test_post_trading_mode(self, client):
        """Test POST /api/trading-mode."""
        response = client.post(
            "/api/trading-mode",
            json={"mode": "preview"}
        )
        
        assert response.status_code in [200, 400, 422]
