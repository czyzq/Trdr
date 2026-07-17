"""Web Push subscription endpoints for the PWA."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services import web_push

router = APIRouter()


@router.get("/api/push/vapid-public-key")
async def vapid_public_key():
    return {"key": web_push.get_public_key()}


@router.post("/api/push/subscribe")
async def subscribe(request: Request):
    try:
        sub = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    if not isinstance(sub, dict) or not isinstance(sub.get("endpoint"), str) or not sub["endpoint"]:
        return JSONResponse({"error": "subscription needs a string endpoint"}, status_code=400)
    keys = sub.get("keys")
    if not isinstance(keys, dict) or not keys.get("p256dh") or not keys.get("auth"):
        return JSONResponse({"error": "subscription needs keys with p256dh and auth"}, status_code=400)
    try:
        count = web_push.add_subscription(sub)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"ok": True, "subscriptions": count}


@router.post("/api/push/unsubscribe")
async def unsubscribe(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    endpoint = body.get("endpoint", "") if isinstance(body, dict) else ""
    web_push.remove_subscription(endpoint)
    return {"ok": True}


@router.post("/api/push/test")
async def push_test():
    import asyncio

    sent = await asyncio.to_thread(web_push.send_to_all, "Trdr", "Test notification - push works!", "test")
    return {"ok": True, "sent": sent}
