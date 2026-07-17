"""Daily digest: one push per day with equity, P&L and open positions.

Scheduled from the app lifespan; sends at DIGEST_HOUR local time (default 21).
Disable with the DAILY_DIGEST_ENABLED setting (Mongo settings collection).
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone


def _digest_hour() -> int:
    try:
        return int(os.getenv("DIGEST_HOUR", "21"))
    except ValueError:
        return 21


def seconds_until_next_run(now: datetime, hour: int) -> float:
    """Seconds from `now` until the next occurrence of `hour`:00 local."""
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _today_window_utc(now_local: datetime = None) -> tuple:
    """Local midnight -> now, expressed as UTC ISO strings (trades store
    closed_at as UTC ISO). Keeps the 'today' boundary consistent with the
    scheduler and dedupe key, which both use local time."""
    now_local = (now_local or datetime.now()).astimezone()
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = now_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc.isoformat(timespec="seconds"), end_utc.isoformat(timespec="seconds")


def build_digest() -> str:
    """Compose the digest message from broker state. Cheap - no network calls."""
    from services.state import broker

    account = broker.get_account()
    positions = broker.get_open_positions() if hasattr(broker, "get_open_positions") else []
    closed = broker.get_closed_positions(100) if hasattr(broker, "get_closed_positions") else []

    start_utc, end_utc = _today_window_utc()
    # compare on the first 19 chars ("YYYY-MM-DDTHH:MM:SS") to tolerate
    # trailing "Z"/microseconds in stored timestamps
    todays = [t for t in closed if start_utc <= (t.get("closed_at") or "")[:19] <= end_utc]
    day_pnl = sum(t.get("pnl_usd", 0) for t in todays)
    wins = sum(1 for t in todays if t.get("pnl_usd", 0) > 0)

    equity = account.get("equity_usd", account.get("balance_usd", 0))
    balance = account.get("balance_usd", 0)
    total_pnl = account.get("total_pnl_usd", 0)

    lines = [
        "Daily digest",
        f"Equity ${equity:,.2f} | Balance ${balance:,.2f}",
        f"Today: {len(todays)} trades, {wins} wins, P&L ${day_pnl:+,.2f}",
        f"Total P&L ${total_pnl:+,.2f}",
    ]
    if positions:
        lines.append(f"Open positions ({len(positions)}):")
        for p in positions[:5]:
            lines.append(
                f"  {p.get('symbol')} {p.get('direction')} "
                f"{p.get('unrealized_pnl_usd', 0):+,.2f} USD"
            )
    else:
        lines.append("No open positions")
    return "\n".join(lines)


def _enabled() -> bool:
    try:
        import database

        val = database.get_setting("DAILY_DIGEST_ENABLED", 1)
        return bool(int(val)) if val is not None else True
    except Exception:
        return True


async def daily_digest_loop():
    """Background task: sleep until DIGEST_HOUR, send, repeat."""
    from app.logging import log_event
    from services.notifier import notify

    log_event("[DIGEST] Daily digest task started", "info")
    while True:
        wait = seconds_until_next_run(datetime.now(), _digest_hour())
        await asyncio.sleep(wait)
        try:
            if _enabled():
                message = build_digest()
                await notify("daily_digest", message, dedupe_key=f"digest_{datetime.now().date()}")
        except Exception as e:
            log_event(f"[DIGEST] Failed to send: {e}", "warning")
        # guard against clock edge cases re-triggering within the same minute
        await asyncio.sleep(61)
