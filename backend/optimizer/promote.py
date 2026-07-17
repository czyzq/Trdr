"""Guarded promotion pipeline: candidate -> active, with versioning, audit
trail, kill-switch, and one-call rollback.

Settings (Mongo `settings` collection):
- OPTIMIZER_ENABLED (default 1): master switch for running studies
- AUTO_PROMOTE_ENABLED (default 1): may guard-passing candidates go live
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import database

STRATEGIES_JSON = Path(__file__).resolve().parent.parent / "strategies.json"


def _setting(key: str, default=1) -> bool:
    try:
        val = database.get_setting(key, default)
        return bool(int(val)) if val is not None else bool(default)
    except Exception:
        return bool(default)


def optimizer_enabled() -> bool:
    return _setting("OPTIMIZER_ENABLED", 1)


def auto_promote_enabled() -> bool:
    return _setting("AUTO_PROMOTE_ENABLED", 1)


def kill_switch(reason: str) -> None:
    """Disable the loop and record why. Demotion of recent promotions is manual review."""
    try:
        database.set_setting("OPTIMIZER_ENABLED", 0)
        database.set_setting("AUTO_PROMOTE_ENABLED", 0)
    except Exception:
        pass
    _audit("kill_switch", {"reason": reason})


def _mongo():
    try:
        return database.get_db()
    except Exception:
        return None


def _audit(action: str, payload: dict) -> None:
    doc = {"action": action, "at": datetime.utcnow().isoformat(), **payload}
    mongo = _mongo()
    if mongo is not None:
        try:
            mongo.config_audit.insert_one(dict(doc))
            return
        except Exception:
            pass
    print(f"[AUDIT] {json.dumps(doc, default=str)}")


def _next_version(strategy_id: str) -> int:
    mongo = _mongo()
    if mongo is None:
        return 1
    last = mongo.strategy_versions.find_one({"strategy_id": strategy_id}, sort=[("version", -1)])
    return (last["version"] + 1) if last else 1


def promote(strategy_id: str, candidate_config: dict, guard_report: dict,
            source: str = "optimizer") -> Optional[dict]:
    """Version the candidate, mark it active, retire the previous active version,
    regenerate strategies.json, and audit. Returns the version doc or None."""
    if not auto_promote_enabled():
        _audit("promotion_blocked", {"strategy_id": strategy_id, "reason": "AUTO_PROMOTE_ENABLED=0"})
        return None

    version = _next_version(strategy_id)
    doc = {
        "strategy_id": strategy_id,
        "version": version,
        "config": candidate_config,
        "guard_report": guard_report,
        "source": source,
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
    }
    mongo = _mongo()
    if mongo is not None:
        mongo.strategy_versions.update_many(
            {"strategy_id": strategy_id, "status": "active"},
            {"$set": {"status": "retired", "retired_at": datetime.utcnow().isoformat()}},
        )
        mongo.strategy_versions.insert_one(dict(doc))

    _apply_to_strategies_json(strategy_id, candidate_config)
    _audit("promoted", {"strategy_id": strategy_id, "version": version,
                        "guard_report": guard_report})
    return doc


def rollback(strategy_id: str) -> Optional[dict]:
    """Reactivate the previous version (one call)."""
    mongo = _mongo()
    if mongo is None:
        return None
    current = mongo.strategy_versions.find_one({"strategy_id": strategy_id, "status": "active"})
    previous = mongo.strategy_versions.find_one(
        {"strategy_id": strategy_id, "status": "retired"}, sort=[("version", -1)])
    if previous is None:
        return None
    if current:
        mongo.strategy_versions.update_one(
            {"_id": current["_id"]},
            {"$set": {"status": "rolled_back", "rolled_back_at": datetime.utcnow().isoformat()}})
    mongo.strategy_versions.update_one({"_id": previous["_id"]}, {"$set": {"status": "active"}})
    _apply_to_strategies_json(strategy_id, previous["config"])
    _audit("rollback", {"strategy_id": strategy_id, "to_version": previous["version"]})
    return previous


def _apply_to_strategies_json(strategy_id: str, config: dict) -> None:
    """Write the promoted config into strategies.json (replace or append)."""
    try:
        data = json.loads(STRATEGIES_JSON.read_text())
    except Exception:
        data = {"strategies": []}
    config = dict(config)
    config["id"] = strategy_id
    config.setdefault("enabled", True)
    replaced = False
    for i, s in enumerate(data.get("strategies", [])):
        if s.get("id") == strategy_id:
            data["strategies"][i] = config
            replaced = True
            break
    if not replaced:
        data.setdefault("strategies", []).append(config)
    STRATEGIES_JSON.write_text(json.dumps(data, indent=2))
    # hot-reload the in-process manager if it's loaded
    try:
        from services.strategy_manager import get_strategy_manager

        get_strategy_manager(force_reload=True)
    except Exception:
        pass
