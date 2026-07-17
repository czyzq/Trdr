"""Shared-token auth for the API.

Set DASHBOARD_TOKEN in the environment to require authentication on every
/api/* route. Clients authenticate with either:
- Cookie:  trdr_token=<token>   (what the dashboard uses - set once, sent
  automatically with every same-origin request, classic and v2 alike)
- Header:  Authorization: Bearer <token>   (for curl/scripts)

When DASHBOARD_TOKEN is unset, auth is disabled (local development).
Exempt paths stay open: health checks (UptimeRobot) and the static frontend.
"""

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse

COOKIE_NAME = "trdr_token"
EXEMPT_PATHS = {"/health", "/api/health"}


def _expected_token() -> str:
    return os.getenv("DASHBOARD_TOKEN", "")


def _request_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE_NAME, "")


def is_authorized(request: Request) -> bool:
    expected = _expected_token()
    if not expected:
        return True
    supplied = _request_token(request)
    return bool(supplied) and hmac.compare_digest(supplied, expected)


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if (
        path.startswith("/api")
        and path not in EXEMPT_PATHS
        and request.method != "OPTIONS"
        and not is_authorized(request)
    ):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)
