"""Web Push subscription endpoints for the PWA."""

from fastapi import APIRouter, Request

from services import web_push

router = APIRouter()


@router.get("/api/push/vapid-public-key")
async def vapid_public_key():
    return {"key": web_push.get_public_key()}


@router.post("/api/push/subscribe")
async def subscribe(request: Request):
    sub = await request.json()
    try:
        count = web_push.add_subscription(sub)
    except ValueError as e:
        return {"error": str(e)}
    return {"ok": True, "subscriptions": count}


@router.post("/api/push/unsubscribe")
async def unsubscribe(request: Request):
    body = await request.json()
    web_push.remove_subscription(body.get("endpoint", ""))
    return {"ok": True}


@router.post("/api/push/test")
async def push_test():
    import asyncio

    sent = await asyncio.to_thread(web_push.send_to_all, "Trdr", "Test notification - push works!", "test")
    return {"ok": True, "sent": sent}
