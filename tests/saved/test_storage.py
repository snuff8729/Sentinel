import json
from pathlib import Path

from app.saved.storage import write_saved_image


def test_write_image_creates_file(tmp_path):
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"fake image data"
    rel_path = write_saved_image(
        data_dir=tmp_path,
        article_id=42,
        hex_id="abc123",
        image_bytes=image_bytes,
        metadata=None,
    )
    assert rel_path == "saved/42/abc123.png"
    written = (tmp_path / "saved" / "42" / "abc123.png").read_bytes()
    assert written == image_bytes
    assert not (tmp_path / "saved" / "42" / "abc123.json").exists()


def test_write_with_metadata_creates_sidecar(tmp_path):
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"data"
    metadata = {"prompt": "a cat", "steps": 28, "source": "exif_user_comment"}
    write_saved_image(
        data_dir=tmp_path,
        article_id=42,
        hex_id="abc123",
        image_bytes=image_bytes,
        metadata=metadata,
    )
    sidecar = tmp_path / "saved" / "42" / "abc123.json"
    assert sidecar.exists()
    parsed = json.loads(sidecar.read_text(encoding="utf-8"))
    assert parsed == metadata


def test_write_creates_directories_when_missing(tmp_path):
    assert not (tmp_path / "saved").exists()
    write_saved_image(
        data_dir=tmp_path,
        article_id=999,
        hex_id="xyz",
        image_bytes=b"\x89PNG\r\n\x1a\nx",
        metadata=None,
    )
    assert (tmp_path / "saved" / "999" / "xyz.png").exists()
