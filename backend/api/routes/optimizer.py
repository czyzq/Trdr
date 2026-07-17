"""Optimizer / Strategy Lab API routes.

Endpoints:
- GET  /api/optimizer/status
- POST /api/optimizer/kill
- POST /api/optimizer/rollback/{strategy_id}
- POST /api/optimizer/settings
- GET  /api/notifier/status
"""
import os
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import database
from optimizer import promote

router = APIRouter(tags=["optimizer"])


def _jsonable(value):
    """Strip Mongo _id fields and coerce non-JSON-serializable values to str."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items() if k != "_id"}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


@router.get("/api/optimizer/status")
async def optimizer_status():
    """Optimizer settings + recent studies and strategy versions."""
    studies = []
    versions = []
    try:
        db = database.get_db()
    except Exception:
        db = None
    if db is not None:
        try:
            studies = [_jsonable(d) for d in db.optimization_studies.find().sort("at", -1).limit(20)]
        except Exception:
            studies = []
        try:
            versions = [_jsonable(d) for d in db.strategy_versions.find().sort("created_at", -1).limit(20)]
        except Exception:
            versions = []
    return {
        "optimizer_enabled": promote.optimizer_enabled(),
        "auto_promote_enabled": promote.auto_promote_enabled(),
        "studies": studies,
        "versions": versions,
    }


@router.post("/api/optimizer/kill")
async def optimizer_kill():
    """Engage the optimizer kill switch (disables studies and auto-promotion)."""
    promote.kill_switch("manual via UI")
    return {"ok": True}


@router.post("/api/optimizer/rollback/{strategy_id}")
async def optimizer_rollback(strategy_id: str):
    """Roll a strategy back to its previous version."""
    previous = promote.rollback(strategy_id)
    if previous is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"No previous version to roll back to for '{strategy_id}'"},
        )
    return {"ok": True, "version": _jsonable(previous)}


class OptimizerSettings(BaseModel):
    optimizer_enabled: Optional[bool] = None
    auto_promote_enabled: Optional[bool] = None


@router.post("/api/optimizer/settings")
async def optimizer_settings(body: OptimizerSettings):
    """Update optimizer master switches."""
    if body.optimizer_enabled is not None:
        database.set_setting("OPTIMIZER_ENABLED", 1 if body.optimizer_enabled else 0)
    if body.auto_promote_enabled is not None:
        database.set_setting("AUTO_PROMOTE_ENABLED", 1 if body.auto_promote_enabled else 0)
    return {
        "optimizer_enabled": promote.optimizer_enabled(),
        "auto_promote_enabled": promote.auto_promote_enabled(),
    }


@router.get("/api/notifier/status")
async def notifier_status():
    """Which notification channels are configured. Sends nothing."""
    telegram_configured = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
    imessage_available = False
    try:
        from imessage_alerts import get_dispatcher

        dispatcher = get_dispatcher()
        imessage_available = bool(dispatcher.config.enabled and dispatcher.config.recipient_phone)
    except Exception:
        imessage_available = False
    push_subscriptions = 0
    try:
        from services import web_push

        push_subscriptions = len(web_push.list_subscriptions())
    except Exception:
        pass
    return {
        "telegram_configured": telegram_configured,
        "imessage_available": imessage_available,
        "push_subscriptions": push_subscriptions,
    }
