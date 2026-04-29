"""Atomic file writes for library-imported images.

Layout: <data_dir>/library/<hex[:2]>/<hex>.<ext> (sharded by hex prefix
to keep directory entry counts low; 256 buckets). Optional NAI metadata
sidecar at <hex>.json in the same directory. Both writes use .tmp + replace
for atomicity."""

from __future__ import annotations

import json
from pathlib import Path


def library_relative_path(hex_id: str, ext: str) -> str:
    return f"library/{hex_id[:2]}/{hex_id}.{ext}"


def write_library_image(
    data_dir: str | Path,
    hex_id: str,
    ext: str,
    image_bytes: bytes,
    metadata: dict | None,
) -> str:
    rel = library_relative_path(hex_id, ext)
    full = Path(data_dir) / rel
    full.parent.mkdir(parents=True, exist_ok=True)

    tmp_img = full.with_suffix(full.suffix + ".tmp")
    tmp_img.write_bytes(image_bytes)
    tmp_img.replace(full)

    if metadata is not None:
        json_path = full.with_suffix(".json")
        tmp_json = json_path.with_suffix(".json.tmp")
        tmp_json.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_json.replace(json_path)

    return rel
