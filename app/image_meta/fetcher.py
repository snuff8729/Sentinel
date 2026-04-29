"""Fetch the head of an image from namu CDN.

Reads up to ~256KB to capture the EXIF chunk; retries up to 1MB if EXIF
isn't found (rare ComfyUI workflows can push EXIF further). Returns the
bytes received or None on any HTTP/network failure.

Appends ?type=orig so the namu CDN returns the original PNG instead of
the transcoded WebP — necessary for detecting NAI metadata in older uploads."""

from __future__ import annotations

import logging
import struct

import httpx

from app.image_meta.parser import _extract_exif_chunk

logger = logging.getLogger(__name__)

_HEAD_BYTES = 256 * 1024
_RETRY_BYTES = 1024 * 1024
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://arca.live/",
}


def fetch_image_head_bytes(url: str) -> bytes | None:
    url = _force_orig(url)
    body = _try_range(url, _HEAD_BYTES)
    if body is None:
        return None
    if _has_metadata_terminator(body):
        return body
    body = _try_range(url, _RETRY_BYTES)
    return body


def _force_orig(url: str) -> str:
    """Append type=orig so namu CDN serves the original PNG, not the transcoded WebP."""
    if "type=orig" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}type=orig"


def _has_metadata_terminator(buf: bytes) -> bool:
    """Did we receive enough bytes to fully determine metadata presence?

    PNG metadata (tEXt/iTXt/eXIf) lives BEFORE the first IDAT chunk; if we've seen
    IDAT, all NAI metadata is in the buffer. WebP metadata (EXIF chunk) is small
    and appears in the early RIFF chunks; if we've seen the EXIF chunk, done."""
    if buf[:8] == b"\x89PNG\r\n\x1a\n":
        return _png_has_idat(buf)
    if len(buf) >= 12 and buf[:4] == b"RIFF" and buf[8:12] == b"WEBP":
        return _extract_exif_chunk(buf) is not None
    return True


def _png_has_idat(buf: bytes) -> bool:
    i = 8
    while i + 8 <= len(buf):
        try:
            (length,) = struct.unpack(">I", buf[i : i + 4])
        except struct.error:
            return False
        if buf[i + 4 : i + 8] == b"IDAT":
            return True
        i += 8 + length + 4
        if i > len(buf):
            return False
    return False


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
