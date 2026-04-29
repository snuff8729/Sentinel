"""Atomic file writes for saved images.

Image goes to <data_dir>/saved/<article_id>/<hex>.png.
Optional NAI metadata sidecar at <hex>.json in the same directory.
Both writes are atomic (.tmp + Path.replace)."""

from __future__ import annotations

import json
from pathlib import Path


def write_saved_image(
    data_dir: str | Path,
    article_id: int,
    hex_id: str,
    image_bytes: bytes,
    metadata: dict | None,
) -> str:
    base = Path(data_dir) / "saved" / str(article_id)
    base.mkdir(parents=True, exist_ok=True)

    img_path = base / f"{hex_id}.png"
    tmp_img = img_path.with_suffix(".png.tmp")
    tmp_img.write_bytes(image_bytes)
    tmp_img.replace(img_path)

    if metadata is not None:
        json_path = base / f"{hex_id}.json"
        tmp_json = json_path.with_suffix(".json.tmp")
        tmp_json.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_json.replace(json_path)

    return f"saved/{article_id}/{hex_id}.png"
