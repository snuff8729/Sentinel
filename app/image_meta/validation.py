"""URL whitelist validation for namu CDN image fetches.

Accepts only http/https URLs whose hostname ends with ".namu.la" and rejects
overlong URLs (>2048 chars) and any URL containing ".." (path traversal)."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import HTTPException

_MAX_URL_LEN = 2048
_ALLOWED_HOST_SUFFIX = ".namu.la"


def validate_url(url: str) -> None:
    if len(url) > _MAX_URL_LEN:
        raise HTTPException(status_code=400, detail="url too long")
    if ".." in url:
        raise HTTPException(status_code=400, detail="url contains traversal")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="url scheme not allowed")
    host = (parsed.hostname or "").lower()
    if not host.endswith(_ALLOWED_HOST_SUFFIX):
        raise HTTPException(status_code=400, detail="url host not allowed")
