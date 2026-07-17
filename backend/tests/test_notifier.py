"""Tests for the notification service (services/notifier.py)."""

import asyncio

import pytest

from services import notifier


class RecorderChannel:
    """Records every message it is asked to send."""

    def __init__(self):
        self.sent = []

    async def send(self, message: str) -> bool:
        self.sent.append(message)
        return True


@pytest.fixture
def recorder(monkeypatch):
    """Reset notifier state and replace real channels with a recorder."""
    notifier._reset_state()
    channel = RecorderChannel()
    monkeypatch.setattr(notifier, "_get_channels", lambda: [channel])
    # deterministic daytime clock by default
    monkeypatch.setattr(notifier, "_local_hour", lambda: 12)
    yield channel
    notifier._reset_state()


def _set_time(monkeypatch, t: float):
    monkeypatch.setattr(notifier, "_now", lambda: t)


def test_dedupe_suppresses_same_key(recorder, monkeypatch):
    _set_time(monkeypatch, 1000.0)
    assert asyncio.run(notifier.notify("trade_opened", "first", dedupe_key="k1")) is True
    # past the rate limit but within the 10-minute dedupe window
    _set_time(monkeypatch, 1030.0)
    assert asyncio.run(notifier.notify("trade_opened", "dup", dedupe_key="k1")) is False
    # a different key still goes through
    assert asyncio.run(notifier.notify("trade_opened", "other", dedupe_key="k2")) is True
    # after the dedupe window the same key sends again
    _set_time(monkeypatch, 1000.0 + notifier.DEDUPE_SECONDS + 1)
    assert asyncio.run(notifier.notify("trade_opened", "again", dedupe_key="k1")) is True
    assert recorder.sent == ["first", "other", "again"]


def test_rate_limit_enforced(recorder, monkeypatch):
    _set_time(monkeypatch, 1000.0)
    assert asyncio.run(notifier.notify("trade_opened", "a")) is True
    _set_time(monkeypatch, 1002.0)  # < 5s later
    assert asyncio.run(notifier.notify("trade_closed", "b")) is False
    _set_time(monkeypatch, 1006.0)  # >= 5s after last send
    assert asyncio.run(notifier.notify("trade_closed", "c")) is True
    assert recorder.sent == ["a", "c"]


def test_quiet_hours_suppress_info_but_not_alerts(recorder, monkeypatch):
    monkeypatch.setattr(notifier, "_local_hour", lambda: 23)
    _set_time(monkeypatch, 1000.0)
    assert asyncio.run(notifier.notify("daily_digest", "digest")) is False
    assert asyncio.run(notifier.notify("trade_closed", "closed")) is True
    _set_time(monkeypatch, 2000.0)
    monkeypatch.setattr(notifier, "_local_hour", lambda: 3)  # still quiet
    assert asyncio.run(notifier.notify("consensus_flip", "flip")) is False
    assert asyncio.run(notifier.notify("kill_switch", "kill")) is True
    # daytime: info events are allowed again
    _set_time(monkeypatch, 3000.0)
    monkeypatch.setattr(notifier, "_local_hour", lambda: 12)
    assert asyncio.run(notifier.notify("daily_digest", "digest2")) is True
    assert recorder.sent == ["closed", "kill", "digest2"]


def test_unconfigured_telegram_is_noop(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    channel = notifier.TelegramChannel()
    assert asyncio.run(channel.send("hello")) is False  # no exception raised


def test_notify_never_raises_with_real_channels(monkeypatch):
    """End-to-end through the real (unconfigured) channels must not raise."""
    notifier._reset_state()
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(notifier, "_local_hour", lambda: 12)
    assert asyncio.run(notifier.notify("health", "ping")) is True
    notifier._reset_state()


def test_notify_sync_without_loop_does_not_raise(recorder, monkeypatch):
    _set_time(monkeypatch, 1000.0)
    notifier.notify_sync("promotion", "promoted", dedupe_key="p1")
    assert recorder.sent == ["promoted"]
