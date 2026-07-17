"""Regression tests for the Phase 1 critical fixes.

Covers:
(a) one failing symbol no longer kills the whole signal scan
(b) leverage is applied to margin only, never to P&L
(c) circuit breaker actually trips (pnl_usd field, ISO-string dates, consecutive losses, daily limit)
(g) INSTRUMENTS has a single source of truth
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from models import SignalDirection


# ── (a) gather isolation ──


def test_neutral_signal_helper():
    from services.trading_engine import _neutral_signal

    sig = _neutral_signal("XAU", 2000.0, "5")
    assert sig.direction == SignalDirection.NEUTRAL
    assert sig.score == 0.0
    assert sig.current_price == 2000.0


def test_one_symbol_error_does_not_kill_scan():
    """One raising symbol must yield a neutral signal, not wipe out the batch."""
    import services.trading_engine as te

    async def fake_analyze(symbol, info, news):
        if symbol == "XAG":
            raise RuntimeError("boom")
        return te._neutral_signal(symbol, 100.0, "5")

    async def run():
        with patch.object(te, "_analyze_single_symbol", side_effect=fake_analyze):
            return await te._generate_signals_internal()

    with patch.object(te, "get_news_client", return_value=None):
        signals = asyncio.run(run())

    from app.config import INSTRUMENTS

    assert len(signals) == len(INSTRUMENTS)
    by_symbol = {s.symbol: s for s in signals}
    assert by_symbol["XAG"].direction == SignalDirection.NEUTRAL
    # the other symbols still produced signals
    assert set(by_symbol) == set(INSTRUMENTS)


# ── (b) leverage convention: P&L = delta_price * size ──


@pytest.mark.asyncio
async def test_pnl_excludes_leverage(fresh_broker):
    broker = fresh_broker
    opened = await broker.open_position(
        symbol="XAU",
        direction="buy",
        size=2.0,
        entry_price=2000.0,
        take_profit=2100.0,
        stop_loss=1900.0,
    )
    assert opened.get("status") == "opened", opened
    pos = opened["position"]
    closed = await broker.close_position(pos["id"], exit_price=2050.0)
    assert closed.get("status") == "closed", closed
    # P&L must be (2050 - 2000) * 2.0 = 100, NOT * leverage (20x would give 2000)
    assert closed["position"]["pnl_usd"] == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_margin_uses_leverage(fresh_broker):
    broker = fresh_broker
    opened = await broker.open_position(
        symbol="XAU",
        direction="buy",
        size=1.0,
        entry_price=2000.0,
        take_profit=2100.0,
        stop_loss=1900.0,
    )
    assert opened.get("status") == "opened", opened
    from app.config import INSTRUMENTS

    lev = INSTRUMENTS["XAU"]["leverage"]
    assert opened["position"]["margin_usd"] == pytest.approx(2000.0 * 1.0 / lev)


# ── (c) circuit breaker ──


def _mk_trade(pnl_usd, hours_ago=1.0):
    return {
        "pnl_usd": pnl_usd,
        "closed_at": (datetime.utcnow() - timedelta(hours=hours_ago)).isoformat(),
        "status": "closed",
    }


def _mongo_with_trades(trades):
    mongo = MagicMock()
    cursor = MagicMock()
    cursor.sort.return_value.limit.return_value = trades
    mongo.trades.find.return_value = cursor
    return mongo


def _healthy_account():
    return {"balance_usd": 3000.0, "equity_usd": 3000.0, "peak_equity_usd": 3000.0}


def test_circuit_breaker_trips_on_consecutive_losses():
    import services.circuit_breaker as cb

    cb.reset_circuit_breaker()
    # newest-first, 5 losses then a win: must trip
    trades = [_mk_trade(-10, i) for i in range(5)] + [_mk_trade(50, 6)]
    with patch("database.get_db", return_value=_mongo_with_trades(trades)), patch(
        "database.get_setting", return_value=20.0
    ), patch("services.state.get_account", return_value=_healthy_account()):
        allowed, reason = cb.check_circuit_breaker()
    assert allowed is False
    assert "consecutive" in reason
    cb.reset_circuit_breaker()


def test_circuit_breaker_win_breaks_streak():
    import services.circuit_breaker as cb

    cb.reset_circuit_breaker()
    # a win between losses: only 3 consecutive -> no trip (limit 5)
    trades = (
        [_mk_trade(-10, i) for i in range(3)]
        + [_mk_trade(50, 4)]
        + [_mk_trade(-10, i) for i in range(5, 10)]
    )
    with patch("database.get_db", return_value=_mongo_with_trades(trades)), patch(
        "database.get_setting", return_value=20.0
    ), patch("services.state.get_account", return_value=_healthy_account()):
        allowed, _ = cb.check_circuit_breaker()
    assert allowed is True
    cb.reset_circuit_breaker()


def test_circuit_breaker_daily_trade_limit():
    import services.circuit_breaker as cb

    cb.reset_circuit_breaker()
    trades = [_mk_trade(5, 0.01 * i) for i in range(cb.MAX_DAILY_TRADES)]
    with patch("database.get_db", return_value=_mongo_with_trades(trades)), patch(
        "database.get_setting", return_value=20.0
    ), patch("services.state.get_account", return_value=_healthy_account()):
        allowed, reason = cb.check_circuit_breaker()
    assert allowed is False
    assert "Daily trade limit" in reason
    cb.reset_circuit_breaker()


def test_circuit_breaker_trips_on_drawdown():
    import services.circuit_breaker as cb

    cb.reset_circuit_breaker()
    account = {"balance_usd": 2000.0, "equity_usd": 2000.0, "peak_equity_usd": 3000.0}
    with patch("database.get_db", return_value=_mongo_with_trades([])), patch(
        "database.get_setting", return_value=20.0
    ), patch("services.state.get_account", return_value=account):
        allowed, reason = cb.check_circuit_breaker()
    assert allowed is False
    assert "drawdown" in reason.lower()
    cb.reset_circuit_breaker()


def test_circuit_breaker_allows_healthy_state():
    import services.circuit_breaker as cb

    cb.reset_circuit_breaker()
    with patch("database.get_db", return_value=_mongo_with_trades([_mk_trade(25.0)])), patch(
        "database.get_setting", return_value=20.0
    ), patch("services.state.get_account", return_value=_healthy_account()):
        allowed, reason = cb.check_circuit_breaker()
    assert allowed is True
    assert reason == ""


# ── (g) single INSTRUMENTS source ──


def test_instruments_single_source():
    from app.config import INSTRUMENTS as config_instruments
    import broker_sim

    assert broker_sim.INSTRUMENTS is config_instruments
    # conservative leverage caps preserved
    assert config_instruments["BTC"]["leverage"] == 2
    assert config_instruments["XAG"]["leverage"] == 10
    # every instrument carries an explicit entry threshold
    assert all("min_score" in cfg for cfg in config_instruments.values())
