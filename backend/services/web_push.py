"""Web Push (VAPID) channel - native push notifications for the home-screen PWA.

Free and self-hosted: keys are generated locally on first start (no external
service). Subscriptions persist in Mongo when available, else a local JSON
file. iOS 16.4+ requires the app to be installed to the home screen and the
page served over HTTPS (localhost is exempt for testing).
"""

import base64
import json
import threading
from pathlib import Path
from typing import List, Optional

_BASE = Path(__file__).resolve().parent.parent
_KEY_FILE = _BASE / "data" / "vapid_private.pem"
_SUBS_FILE = _BASE / "data" / "push_subscriptions.json"
_lock = threading.Lock()
_vapid = None

VAPID_CLAIMS = {"sub": "mailto:trdr@localhost"}


def _get_vapid():
    """Load or create the VAPID keypair.

    Order: local PEM file -> Mongo setting (Render's filesystem is ephemeral,
    so the file vanishes on redeploy) -> generate fresh and persist to BOTH.
    The PEM file is always (re)written because pywebpush reads the key from
    the file path in send_to_all.
    """
    global _vapid
    if _vapid is not None:
        return _vapid
    from py_vapid import Vapid01

    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    v = None
    if _KEY_FILE.exists():
        v = Vapid01.from_file(str(_KEY_FILE))
    else:
        # File gone (fresh deploy) - try the PEM persisted in Mongo
        pem = None
        try:
            import database

            pem = database.get_setting("VAPID_PRIVATE_PEM")
        except Exception:
            pem = None
        if isinstance(pem, str) and "-----BEGIN" in pem:
            v = Vapid01.from_pem(pem.encode("utf8"))
            try:
                _KEY_FILE.write_text(pem)
            except Exception:
                pass
        else:
            v = Vapid01()
            v.generate_keys()
            v.save_key(str(_KEY_FILE))
            try:
                import database

                database.set_setting("VAPID_PRIVATE_PEM", v.private_pem().decode("utf8"))
            except Exception:
                pass
    _vapid = v
    return v


def get_public_key() -> str:
    """Uncompressed EC point, base64url - the browser's applicationServerKey."""
    from cryptography.hazmat.primitives import serialization

    v = _get_vapid()
    raw = v.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


# ── subscription store: Mongo -> file fallback ──


def _mongo():
    try:
        import database

        return database.get_db()
    except Exception:
        return None


def _load_file_subs() -> List[dict]:
    try:
        return json.loads(_SUBS_FILE.read_text())
    except Exception:
        return []


def _save_file_subs(subs: List[dict]) -> None:
    _SUBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SUBS_FILE.write_text(json.dumps(subs, indent=2))


def add_subscription(sub: dict) -> int:
    """Idempotent by endpoint URL. Returns total subscription count."""
    endpoint = sub.get("endpoint")
    if not endpoint:
        raise ValueError("subscription needs an endpoint")
    mongo = _mongo()
    if mongo is not None:
        mongo.push_subscriptions.update_one(
            {"endpoint": endpoint}, {"$set": {"endpoint": endpoint, "subscription": sub}}, upsert=True
        )
        return mongo.push_subscriptions.count_documents({})
    with _lock:
        subs = [s for s in _load_file_subs() if s.get("endpoint") != endpoint]
        subs.append({"endpoint": endpoint, "subscription": sub})
        _save_file_subs(subs)
        return len(subs)


def remove_subscription(endpoint: str) -> None:
    mongo = _mongo()
    if mongo is not None:
        mongo.push_subscriptions.delete_one({"endpoint": endpoint})
        return
    with _lock:
        _save_file_subs([s for s in _load_file_subs() if s.get("endpoint") != endpoint])


def list_subscriptions() -> List[dict]:
    mongo = _mongo()
    if mongo is not None:
        return [d["subscription"] for d in mongo.push_subscriptions.find({}, {"_id": 0})]
    return [s["subscription"] for s in _load_file_subs()]


def send_to_all(title: str, body: str, tag: Optional[str] = None) -> int:
    """Send a push to every subscription; prunes dead ones (410/404). Returns sent count."""
    from pywebpush import WebPushException, webpush

    v = _get_vapid()
    payload = json.dumps({"title": title, "body": body, "tag": tag or "trdr"})
    sent = 0
    failed = 0
    last_error = None
    for sub in list_subscriptions():
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=str(_KEY_FILE),
                vapid_claims=dict(VAPID_CLAIMS),
            )
            sent += 1
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                remove_subscription(sub.get("endpoint", ""))
            else:
                failed += 1
                last_error = f"status={status} {e}"
        except Exception:
            pass
    if failed:
        # one aggregated line, not one per subscription
        msg = f"[WEB-PUSH] {failed} push send(s) failed (last: {last_error})"
        try:
            from app.logging import log_event

            log_event(msg, "warning")
        except Exception:
            print(msg)
    return sent
