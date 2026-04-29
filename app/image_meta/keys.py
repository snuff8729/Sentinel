"""Cache/storage key helpers for image metadata + saved images.

`extract_hex_from_url` extracts the namu CDN content hash (64-char hex segment)
from a URL, or falls back to a sha1 of the entire URL when no hex is present."""

from __future__ import annotations

import hashlib
import re

_HEX64_RE = re.compile(r"[a-fA-F0-9]{64}")


def extract_hex_from_url(url: str) -> str:
    m = _HEX64_RE.search(url)
    if m:
        return m.group(0).lower()
    return hashlib.sha1(url.encode("utf-8")).hexdigest()
