"""Tests for LibraryService.import_image: dedup, EXIF extraction, file copy, row insert."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

from sqlmodel import Session, select

from app.db.engine import create_engine_and_tables
from app.db.models import SavedImage
from app.saved.library import LibraryService


def _make_service(tmp_path: Path):
    engine = create_engine_and_tables("sqlite:///:memory:")
    return LibraryService(engine=engine, data_dir=str(tmp_path)), engine


def _png_bytes(text_chunks: dict[bytes, bytes] | None = None) -> bytes:
    """Build a minimal valid PNG with optional tEXt chunks."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data))
    chunks = b""
    for k, v in (text_chunks or {}).items():
        body = k + b"\x00" + v
        chunks += struct.pack(">I", len(body)) + b"tEXt" + body + struct.pack(">I", zlib.crc32(b"tEXt" + body))
    idat_body = zlib.compress(b"\x00\x00")
    idat = struct.pack(">I", len(idat_body)) + b"IDAT" + idat_body + struct.pack(">I", zlib.crc32(b"IDAT" + idat_body))
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND"))
    return sig + ihdr + chunks + idat + iend


def test_import_image_creates_completed_row_with_source_library(tmp_path: Path):
    service, engine = _make_service(tmp_path)
    src = tmp_path / "src.png"
    src.write_bytes(_png_bytes())

    result = service.import_image(src)

    assert result["status"] == "imported"
    assert isinstance(result["id"], int)
    with Session(engine) as s:
        rows = s.exec(select(SavedImage)).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.source == "library"
    assert row.article_id == 0
    assert row.status == "completed"
    assert row.completed_at is not None
    assert row.file_path is not None and row.file_path.startswith("library/")


def test_import_image_dedups_by_content_hash(tmp_path: Path):
    service, engine = _make_service(tmp_path)
    content = _png_bytes()
    src1 = tmp_path / "a.png"
    src2 = tmp_path / "b.png"
    src1.write_bytes(content)
    src2.write_bytes(content)

    first = service.import_image(src1)
    second = service.import_image(src2)

    assert first["status"] == "imported"
    assert second["status"] == "already_imported"
    assert second["id"] == first["id"]
    with Session(engine) as s:
        assert len(s.exec(select(SavedImage)).all()) == 1


def test_import_image_extracts_nai_exif_when_present(tmp_path: Path):
    service, engine = _make_service(tmp_path)
    flat = json.dumps({"prompt": "1girl, solo", "steps": 28, "scale": 5.0})
    content = _png_bytes({b"Comment": flat.encode("utf-8")})
    src = tmp_path / "nai.png"
    src.write_bytes(content)

    result = service.import_image(src)

    assert result["status"] == "imported"
    with Session(engine) as s:
        row = s.get(SavedImage, result["id"])
    assert row.payload_json is not None
    parsed = json.loads(row.payload_json)
    assert parsed["prompt"] == "1girl, solo"
    assert parsed["steps"] == 28
    sidecar = tmp_path / row.file_path.replace(".png", ".json")
    assert sidecar.exists()


def test_import_image_writes_no_sidecar_when_no_metadata(tmp_path: Path):
    service, engine = _make_service(tmp_path)
    src = tmp_path / "plain.png"
    src.write_bytes(_png_bytes())

    result = service.import_image(src)

    with Session(engine) as s:
        row = s.get(SavedImage, result["id"])
    assert row.payload_json is None
    sidecar = tmp_path / row.file_path.replace(".png", ".json")
    assert not sidecar.exists()


def test_import_image_skips_unsupported_extension(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    src = tmp_path / "doc.txt"
    src.write_bytes(b"hello")

    result = service.import_image(src)

    assert result["status"] == "skipped"
    assert "ext" in result["reason"].lower() or "unsupported" in result["reason"].lower()


def test_import_image_returns_skipped_when_file_missing(tmp_path: Path):
    service, _ = _make_service(tmp_path)
    result = service.import_image(tmp_path / "nope.png")
    assert result["status"] == "skipped"


def test_import_image_uses_sha256_of_content_as_hex(tmp_path: Path):
    service, engine = _make_service(tmp_path)
    content = _png_bytes()
    expected_hex = hashlib.sha256(content).hexdigest()
    src = tmp_path / "x.png"
    src.write_bytes(content)

    result = service.import_image(src)

    with Session(engine) as s:
        row = s.get(SavedImage, result["id"])
    assert row.hex == expected_hex
