"""Tests for the shared-token auth middleware and the daily digest."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# ── auth ──


def _client():
    from fastapi.testclient import TestClient

    import main

    return TestClient(main.app)


def test_auth_disabled_when_no_token(monkeypatch):
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    client = _client()
    assert client.get("/api/auth/check").status_code == 200


def test_api_locked_without_token(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "s3cret")
    client = _client()
    res = client.get("/api/auth/check")
    assert res.status_code == 401
    assert res.json() == {"error": "unauthorized"}


def test_health_exempt(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "s3cret")
    client = _client()
    # /health stays open for uptime monitors; /api/health is exempt too (404, not 401)
    assert client.get("/health").status_code == 200
    assert client.get("/api/health").status_code != 401


def test_cookie_authorizes(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "s3cret")
    client = _client()
    client.cookies.set("trdr_token", "s3cret")
    assert client.get("/api/auth/check").status_code == 200


def test_bearer_header_authorizes(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "s3cret")
    client = _client()
    res = client.get("/api/auth/check", headers={"Authorization": "Bearer s3cret"})
    assert res.status_code == 200


def test_wrong_token_rejected(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "s3cret")
    client = _client()
    client.cookies.set("trdr_token", "wrong")
    assert client.get("/api/auth/check").status_code == 401


def test_401_response_carries_cors_headers(monkeypatch):
    """CORS must be the outermost middleware: an unauthorized cross-origin
    request still gets access-control-allow-origin so the browser can read
    the 401 instead of reporting an opaque network error."""
    monkeypatch.setenv("DASHBOARD_TOKEN", "s3cret")
    client = _client()
    res = client.get("/api/auth/check", headers={"Origin": "http://localhost:5173"})
    assert res.status_code == 401
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


# ── digest ──


def test_seconds_until_next_run_today_and_tomorrow():
    from services.digest import seconds_until_next_run

    now = datetime(2026, 1, 5, 20, 0, 0)
    assert seconds_until_next_run(now, 21) == pytest.approx(3600)
    now_late = datetime(2026, 1, 5, 22, 0, 0)
    assert seconds_until_next_run(now_late, 21) == pytest.approx(23 * 3600)


def _utc_ts_in_local_today(frac: float) -> str:
    """A UTC ISO timestamp at `frac` of the way through the local day so far.
    Always inside build_digest's window (local midnight -> now, in UTC)."""
    now_local = datetime.now().astimezone()
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    t = start_local + (now_local - start_local) * frac
    return t.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def test_build_digest_message():
    from services import digest

    broker = MagicMock()
    broker.get_account.return_value = {
        "equity_usd": 3120.5, "balance_usd": 3100.0, "total_pnl_usd": 100.0}
    broker.get_closed_positions.return_value = [
        {"pnl_usd": 40.0, "closed_at": _utc_ts_in_local_today(0.25)},
        {"pnl_usd": -15.0, "closed_at": _utc_ts_in_local_today(0.5)},
        {"pnl_usd": 99.0, "closed_at": "2020-01-01T00:00:00"},  # not today
    ]
    broker.get_open_positions.return_value = [
        {"symbol": "BTC", "direction": "buy", "unrealized_pnl_usd": 12.3}]

    with patch("services.state.broker", broker):
        msg = digest.build_digest()

    assert "Equity $3,120.50" in msg
    assert "2 trades, 1 wins" in msg
    assert "+25.00" in msg          # day P&L: 40 - 15
    assert "BTC buy +12.30" in msg
