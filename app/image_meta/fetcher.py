"""Fetch the head of an image from namu CDN.

Reads up to ~256KB to capture the EXIF chunk; retries up to 1MB if EXIF
isn't found (rare ComfyUI workflows can push EXIF further). Returns the
bytes received or None on any HTTP/network failure."""

from __future__ import annotations

import logging
import struct

import httpx

logger = logging.getLogger(__name__)

_HEAD_BYTES = 256 * 1024
_RETRY_BYTES = 1024 * 1024
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://arca.live/",
}


def fetch_image_head_bytes(url: str) -> bytes | None:
    body = _try_range(url, _HEAD_BYTES)
    if body is None:
        return None
    if _has_exif_chunk(body):
        return body
    body = _try_range(url, _RETRY_BYTES)
    return body


def _try_range(url: str, n: int) -> bytes | None:
    headers = dict(_HEADERS)
    headers["Range"] = f"bytes=0-{n - 1}"
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            r = client.get(url, headers=headers)
    except httpx.HTTPError as e:
        logger.warning("image-meta fetch failed: %s (%s)", url[:100], e)
        return None
    if r.status_code not in (200, 206):
        logger.warning("image-meta non-2xx %s: %s", r.status_code, url[:100])
        return None
    return r.content


def _has_exif_chunk(buf: bytes) -> bool:
    if len(buf) < 12 or buf[:4] != b"RIFF" or buf[8:12] != b"WEBP":
        return False
    i = 12
    while i + 8 <= len(buf):
        fourcc = buf[i : i + 4]
        (size,) = struct.unpack("<I", buf[i + 4 : i + 8])
        if fourcc == b"EXIF":
            return True
        i += 8 + size + (size & 1)
    return False
