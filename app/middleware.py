"""HTTP middlewares.

`no_cache_on_error` sets `Cache-Control: no-store` on 4xx/5xx responses so
upstream caches (Cloudflare, browsers) don't pin a transient error response
— e.g., a 404 served while data was being relocated. Origin 2xx responses
keep whatever cache headers they already had."""

from __future__ import annotations

from starlette.requests import Request


async def no_cache_on_error(request: Request, call_next):
    response = await call_next(request)
    if response.status_code >= 400:
        response.headers["Cache-Control"] = "no-store"
    return response
