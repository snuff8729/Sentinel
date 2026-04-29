"""Tests for write_library_image: sharded layout, atomic writes, JSON sidecar."""

from __future__ import annotations

import json
from pathlib import Path

from app.saved.library_storage import library_relative_path, write_library_image


HEX = "ab" + "c" * 62  # 64 hex chars, prefix 'ab'


def test_relative_path_shards_by_first_two_chars():
    assert library_relative_path(HEX, "png") == f"library/ab/{HEX}.png"


def test_write_creates_sharded_dir_and_file(tmp_path: Path):
    rel = write_library_image(str(tmp_path), HEX, "png", b"\x89PNG-fake", None)
    full = tmp_path / rel
    assert full.exists()
    assert full.read_bytes() == b"\x89PNG-fake"
    assert full.parent.name == "ab"
    assert full.parent.parent.name == "library"


def test_write_leaves_no_tmp_files(tmp_path: Path):
    write_library_image(str(tmp_path), HEX, "jpg", b"jpeg-fake", None)
    leftovers = list(tmp_path.rglob("*.tmp"))
    assert leftovers == []


def test_write_creates_json_sidecar_when_metadata_present(tmp_path: Path):
    meta = {"prompt": "test", "seed": 42}
    write_library_image(str(tmp_path), HEX, "png", b"png-bytes", meta)
    json_path = tmp_path / f"library/ab/{HEX}.json"
    assert json_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8")) == meta


def test_write_skips_json_when_metadata_none(tmp_path: Path):
    write_library_image(str(tmp_path), HEX, "png", b"png-bytes", None)
    json_path = tmp_path / f"library/ab/{HEX}.json"
    assert not json_path.exists()
