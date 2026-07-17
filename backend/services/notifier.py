"""Notification service: Telegram / iMessage channels with a log fallback.

Behavior:
- rate limit: at most one send per RATE_LIMIT_SECONDS globally
- dedupe: the same dedupe_key is suppressed for DEDUPE_SECONDS after a send
- quiet hours (23:00-07:00 local): only "info" severity events are suppressed;
  trade_opened / trade_closed / promotion / rollback / kill_switch / health
  are always sent. daily_digest and consensus_flip are info.

All channels are best-effort: an unconfigured or failing channel is a no-op,
and every notification is always mirrored to the in-app event log.
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Dict, Optional

import httpx

from app.logging import log_event

INFO_EVENTS = {"daily_digest", "consensus_flip"}
RATE_LIMIT_SECONDS = 5.0
DEDUPE_SECONDS = 600.0
QUIET_START_HOUR = 23  # inclusive
QUIET_END_HOUR = 7     # exclusive

# module state (tests reset via _reset_state)
_last_sent_at: float = 0.0
_dedupe: Dict[str, float] = {}


def _now() -> float:
    """Monotonic-ish clock; separate function so tests can monkeypatch it."""
    return time.time()


def _local_hour() -> int:
    """Local hour; separate function so tests can monkeypatch it."""
    return datetime.now().hour


def _in_quiet_hours() -> bool:
    hour = _local_hour()
    return hour >= QUIET_START_HOUR or hour < QUIET_END_HOUR


def _reset_state() -> None:
    """Test helper: clear rate-limit and dedupe state."""
    global _last_sent_at
    _last_sent_at = 0.0
    _dedupe.clear()


class TelegramChannel:
    """Telegram bot channel. No-op when TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID unset."""

    async def send(self, message: str) -> bool:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": message},
                )
            return resp.status_code == 200
        except Exception:
            return False


class IMessageChannel:
    """Wraps the existing iMessage dispatcher (Mac-only). No-op on any failure."""

    async def send(self, message: str) -> bool:
        try:
            from imessage_alerts import get_dispatcher

            dispatcher = get_dispatcher()
            if not dispatcher.config.enabled or not dispatcher.config.recipient_phone:
                return False
            result = await asyncio.to_thread(dispatcher._send_via_openclaw, message)
            return (result or {}).get("status") == "sent"
        except Exception:
            return False


def _get_channels():
    """Channel list; separate function so tests can monkeypatch it."""
    return [TelegramChannel(), IMessageChannel()]


async def notify(event_type: str, message: str, dedupe_key: Optional[str] = None) -> bool:
    """Send a notification through all channels. Returns True if dispatched.

    Never raises: every failure degrades to the log fallback.
    """
    global _last_sent_at
    try:
        now = _now()
        severity = "info" if event_type in INFO_EVENTS else "alert"

        if severity == "info" and _in_quiet_hours():
            log_event(f"[NOTIFY suppressed: quiet hours] {event_type}: {message}", "info")
            return False

        if dedupe_key is not None:
            last = _dedupe.get(dedupe_key)
            if last is not None and now - last < DEDUPE_SECONDS:
                return False

        if now - _last_sent_at < RATE_LIMIT_SECONDS:
            log_event(f"[NOTIFY suppressed: rate limit] {event_type}: {message}", "info")
            return False

        _last_sent_at = now
        if dedupe_key is not None:
            _dedupe[dedupe_key] = now

        # Fallback channel: always mirror to the in-app event log.
        log_event(f"[NOTIFY] {event_type}: {message}", "event")

        for channel in _get_channels():
            try:
                await channel.send(message)
            except Exception:
                pass
        return True
    except Exception:
        return False


def notify_sync(event_type: str, message: str, dedupe_key: Optional[str] = None) -> None:
    """Best-effort notify from synchronous code. Never raises.

    Schedules a task when an event loop is running, otherwise runs its own.
    """
    coro = notify(event_type, message, dedupe_key)
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            loop.create_task(coro)
        else:
            asyncio.run(coro)
    except Exception:
        try:
            coro.close()  # avoid "coroutine was never awaited" warnings
        except Exception:
            pass
