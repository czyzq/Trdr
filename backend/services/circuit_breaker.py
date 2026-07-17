"""Circuit breaker service - extracted from main.py"""
from typing import Tuple
from datetime import datetime, timedelta

# Circuit breaker state
_circuit_breaker_triggered = False
_circuit_breaker_reason = ""
_circuit_breaker_since = None

# Configuration
MAX_CONSECUTIVE_LOSSES = 5
MAX_DAILY_TRADES = 20
# MAX_DRAWDOWN_PERCENT is now loaded from db settings (default 20%)


def check_circuit_breaker() -> Tuple[bool, str]:
    """
    Check if trading should be paused due to risk limits.
    Returns (can_trade, reason).
    - can_trade=True: trading is allowed
    - can_trade=False: trading is blocked
    """
    global _circuit_breaker_triggered, _circuit_breaker_reason, _circuit_breaker_since

    import database
    from database import get_db
    from services.state import get_account

    # Get MAX_DRAWDOWN_PERCENT from settings (default 20%)
    max_drawdown = 20.0
    try:
        setting = database.get_setting("MAX_DRAWDOWN_PCT", 20.0)
        max_drawdown = float(setting) if setting else 20.0
    except Exception:
        pass

    # Check if manually triggered
    if _circuit_breaker_triggered:
        # Auto-reset after 1 hour
        if _circuit_breaker_since and datetime.now() - _circuit_breaker_since > timedelta(hours=1):
            reset_circuit_breaker()
            return True, ""
        return False, _circuit_breaker_reason

    # closed_at is stored as an ISO-8601 string (broker_sim uses utcnow().isoformat()),
    # so compare against an ISO string, not a datetime.
    now_utc = datetime.utcnow()
    try:
        mongo = get_db()
        recent_trades = []
        if mongo is not None:
            cutoff_iso = (now_utc - timedelta(hours=24)).isoformat()
            recent_trades = list(mongo.trades.find({
                "closed_at": {"$gte": cutoff_iso}
            }).sort("closed_at", -1).limit(50))

        # Truly consecutive losses: walk newest -> oldest until the first winner
        consecutive_losses = 0
        for t in recent_trades:
            if t.get("pnl_usd", t.get("pnl", 0)) < 0:
                consecutive_losses += 1
            else:
                break
        if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            trigger_circuit_breaker(f"{consecutive_losses} consecutive losses")
            return False, _circuit_breaker_reason

        # Daily trade limit
        day_start_iso = now_utc.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        trades_today = sum(1 for t in recent_trades if (t.get("closed_at") or "") >= day_start_iso)
        if trades_today >= MAX_DAILY_TRADES:
            trigger_circuit_breaker(f"Daily trade limit reached ({trades_today}/{MAX_DAILY_TRADES})")
            return False, _circuit_breaker_reason
    except Exception:
        pass

    # Check drawdown against the live account, not an import-time snapshot
    try:
        account = get_account()
        peak = account.get("peak_equity_usd", account.get("balance_usd", 3000))
        current = account.get("equity_usd", account.get("balance_usd", 3000))
        if peak > 0:
            drawdown = ((peak - current) / peak) * 100
            if drawdown > max_drawdown:
                trigger_circuit_breaker(f"Max drawdown exceeded: {drawdown:.1f}%")
                return False, _circuit_breaker_reason
    except Exception:
        pass

    return True, ""


def trigger_circuit_breaker(reason: str) -> None:
    """Manually trigger circuit breaker."""
    global _circuit_breaker_triggered, _circuit_breaker_reason, _circuit_breaker_since
    _circuit_breaker_triggered = True
    _circuit_breaker_reason = reason
    _circuit_breaker_since = datetime.now()
    # Recovery posture for when the breaker auto-resets: halve position sizes
    # and demand stronger signals until things prove healthy again.
    try:
        from services.state import get_account

        account = get_account()
        account["_risk_multiplier"] = 0.5
        account["_min_score_boost"] = 0.1
    except Exception:
        pass


def reset_circuit_breaker() -> None:
    """Reset circuit breaker (risk adjustments stay until cleared)."""
    global _circuit_breaker_triggered, _circuit_breaker_reason, _circuit_breaker_since
    _circuit_breaker_triggered = False
    _circuit_breaker_reason = ""
    _circuit_breaker_since = None


def clear_risk_adjustments() -> None:
    """Back to full size/thresholds after a healthy recovery period."""
    try:
        from services.state import get_account

        account = get_account()
        account.pop("_risk_multiplier", None)
        account.pop("_min_score_boost", None)
    except Exception:
        pass


def get_circuit_breaker_status() -> dict:
    """Get current circuit breaker status."""
    return {
        "triggered": _circuit_breaker_triggered,
        "reason": _circuit_breaker_reason,
        "since": _circuit_breaker_since.isoformat() if _circuit_breaker_since else None,
    }
