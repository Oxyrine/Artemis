"""API hardening: security headers, HTTPS redirect (when asked), a small in-memory rate limiter for the expensive
endpoints, and an optional bearer token for the hosted copy's write routes."""
from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
HEADERS = {"Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
           "Referrer-Policy": "no-referrer", "Cross-Origin-Opener-Policy": "same-origin",
           "Permissions-Policy": "camera=(), microphone=(), geolocation=()"}


class ApiError(Exception):
    """Every error the API returns has the shape {"error": code, "detail": message}."""

    def __init__(self, status: int, error: str, detail: str):
        super().__init__(detail)
        self.status, self.error, self.detail = status, error, detail


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        force_https = os.environ.get("FORCE_HTTPS") == "1"
        if force_https and request.headers.get("x-forwarded-proto", request.url.scheme) == "http":
            return RedirectResponse(str(request.url.replace(scheme="https")), status_code=308)
        resp = await call_next(request)
        for k, v in HEADERS.items():
            resp.headers.setdefault(k, v)
        if force_https:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp


class RateLimiter:
    """Sliding window per client and bucket. ponytail: per-process memory; use the host's edge limiter if scaled out."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)

    def check(self, request: Request, bucket: str, limit: int, seconds: int = 60) -> None:
        fwd = request.headers.get("x-forwarded-for", "")
        who = fwd.split(",")[0].strip() or (request.client.host if request.client else "?")
        q, now = self._hits[(who, bucket)], time.monotonic()
        while q and now - q[0] > seconds:
            q.popleft()
        if len(q) >= limit:
            raise ApiError(429, "rate_limited", f"too many {bucket} requests; try again in a minute")
        q.append(now)


def require_token(request: Request) -> None:
    """If ARTEMIS_API_TOKEN is set, write routes need 'Authorization: Bearer <token>'. Reads stay open (public demo)."""
    token = os.environ.get("ARTEMIS_API_TOKEN")
    if not token:
        return
    given = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(given, token):
        raise ApiError(401, "unauthorized", "a valid bearer token is required for this action")
