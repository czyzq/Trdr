"""
Tests for the optimizer / Strategy Lab API endpoints.

Run: python -m pytest tests/test_optimizer_api.py -v
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client():
    """Create test client with a mocked broker (same pattern as test_api.py)."""
    mock_broker = MagicMock()
    mock_broker.get_open_positions.return_value = []
    mock_broker.get_closed_positions.return_value = []
    mock_broker.mode = "simulation"

    with patch("main.broker", mock_broker):
        from main import app

        yield TestClient(app)


def _mock_collection(docs):
    """Mock a collection whose find().sort().limit() returns docs."""
    coll = MagicMock()
    coll.find.return_value.sort.return_value.limit.return_value = list(docs)
    return coll


class TestOptimizerStatus:
    def test_status_no_db(self, client):
        """With no DB, lists are empty and settings come from defaults."""
        with patch("database.get_db", return_value=None), \
             patch("database.get_setting", return_value=1):
            response = client.get("/api/optimizer/status")

        assert response.status_code == 200
        data = response.json()
        assert data["optimizer_enabled"] is True
        assert data["auto_promote_enabled"] is True
        assert data["studies"] == []
        assert data["versions"] == []

    def test_status_with_db_strips_mongo_ids(self, client):
        """Studies/versions come back without _id and non-JSON values as str."""
        study = {"_id": object(), "strategy_id": "s1", "passed": True, "best_value": 1.2, "at": "2026-01-01"}
        version = {"_id": object(), "strategy_id": "s1", "version": 3, "status": "active"}
        mock_db = MagicMock()
        mock_db.optimization_studies = _mock_collection([study])
        mock_db.strategy_versions = _mock_collection([version])

        with patch("database.get_db", return_value=mock_db), \
             patch("database.get_setting", side_effect=lambda key, default=None: 0):
            response = client.get("/api/optimizer/status")

        assert response.status_code == 200
        data = response.json()
        assert data["optimizer_enabled"] is False
        assert data["auto_promote_enabled"] is False
        assert data["studies"] == [{"strategy_id": "s1", "passed": True, "best_value": 1.2, "at": "2026-01-01"}]
        assert data["versions"] == [{"strategy_id": "s1", "version": 3, "status": "active"}]


class TestOptimizerKill:
    def test_kill_calls_kill_switch(self, client):
        with patch("optimizer.promote.kill_switch") as mock_kill:
            response = client.post("/api/optimizer/kill")

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_kill.assert_called_once_with("manual via UI")


class TestOptimizerRollback:
    def test_rollback_not_found(self, client):
        with patch("optimizer.promote.rollback", return_value=None):
            response = client.post("/api/optimizer/rollback/missing_strategy")

        assert response.status_code == 404
        assert "error" in response.json()

    def test_rollback_success(self, client):
        previous = {"_id": object(), "strategy_id": "s1", "version": 2, "status": "active", "config": {"a": 1}}
        with patch("optimizer.promote.rollback", return_value=previous) as mock_rb:
            response = client.post("/api/optimizer/rollback/s1")

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["version"]["version"] == 2
        assert "_id" not in data["version"]
        mock_rb.assert_called_once_with("s1")


class TestOptimizerSettings:
    def test_update_both_settings(self, client):
        with patch("database.set_setting") as mock_set, \
             patch("database.get_setting", side_effect=lambda key, default=None: 0):
            response = client.post(
                "/api/optimizer/settings",
                json={"optimizer_enabled": False, "auto_promote_enabled": False},
            )

        assert response.status_code == 200
        calls = {c.args[0]: c.args[1] for c in mock_set.call_args_list}
        assert calls == {"OPTIMIZER_ENABLED": 0, "AUTO_PROMOTE_ENABLED": 0}

    def test_partial_update_only_sets_given_key(self, client):
        with patch("database.set_setting") as mock_set, \
             patch("database.get_setting", side_effect=lambda key, default=None: 1):
            response = client.post("/api/optimizer/settings", json={"optimizer_enabled": True})

        assert response.status_code == 200
        mock_set.assert_called_once_with("OPTIMIZER_ENABLED", 1)


class TestNotifierStatus:
    def test_notifier_status_unconfigured(self, client):
        env = {k: v for k, v in os.environ.items()
               if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
        with patch.dict(os.environ, env, clear=True):
            response = client.get("/api/notifier/status")

        assert response.status_code == 200
        data = response.json()
        assert data["telegram_configured"] is False
        assert isinstance(data["imessage_available"], bool)

    def test_notifier_status_telegram_configured(self, client):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}):
            response = client.get("/api/notifier/status")

        assert response.status_code == 200
        assert response.json()["telegram_configured"] is True
