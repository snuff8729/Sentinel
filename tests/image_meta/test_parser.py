from pathlib import Path

from app.image_meta.parser import parse_has_nai
from app.image_meta.parser import parse_nai_metadata

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parses_real_nai_webp_as_true():
    data = (FIXTURE_DIR / "nai_sample.webp").read_bytes()
    assert parse_has_nai(data) is True


def test_non_webp_bytes_return_false():
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    assert parse_has_nai(png_header) is False


def test_webp_without_exif_returns_false():
    riff_size = 4 + 8 + 10  # WEBP fourcc(4) + VP8X chunk header(8) + VP8X body(10)
    buf = b"RIFF" + riff_size.to_bytes(4, "little") + b"WEBP"
    buf += b"VP8X" + (10).to_bytes(4, "little") + b"\x00" * 10
    assert parse_has_nai(buf) is False


def test_webp_with_exif_but_not_nai_returns_false():
    exif_payload = b"Exif\x00\x00not a tiff header at all, just garbage"
    chunk_size = len(exif_payload)
    pad = chunk_size & 1
    rest = b"WEBP"
    rest += b"VP8X" + (10).to_bytes(4, "little") + b"\x00" * 10
    rest += b"EXIF" + chunk_size.to_bytes(4, "little") + exif_payload + (b"\x00" * pad)
    buf = b"RIFF" + len(rest).to_bytes(4, "little") + rest
    assert parse_has_nai(buf) is False


def test_truncated_bytes_return_false():
    assert parse_has_nai(b"") is False
    assert parse_has_nai(b"RIFF") is False
    assert parse_has_nai(b"RIFF\x10\x00\x00\x00WEBP") is False


def test_parse_nai_metadata_returns_dict_with_core_fields():
    data = (FIXTURE_DIR / "nai_sample.webp").read_bytes()
    meta = parse_nai_metadata(data)
    assert meta is not None
    assert isinstance(meta, dict)
    assert isinstance(meta.get("prompt"), str) and len(meta["prompt"]) > 0
    assert isinstance(meta.get("steps"), int)
    assert isinstance(meta.get("seed"), int)
    assert isinstance(meta.get("sampler"), str)
    assert meta.get("source") == "exif_user_comment"


def test_parse_nai_metadata_returns_none_for_non_webp():
    assert parse_nai_metadata(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64) is None


def test_parse_nai_metadata_returns_none_for_garbage_exif():
    exif_payload = b"Exif\x00\x00not a tiff header at all, just garbage"
    chunk_size = len(exif_payload)
    pad = chunk_size & 1
    rest = b"WEBP"
    rest += b"VP8X" + (10).to_bytes(4, "little") + b"\x00" * 10
    rest += b"EXIF" + chunk_size.to_bytes(4, "little") + exif_payload + (b"\x00" * pad)
    buf = b"RIFF" + len(rest).to_bytes(4, "little") + rest
    assert parse_nai_metadata(buf) is None


def test_parse_has_nai_still_works_via_wrapper():
    data = (FIXTURE_DIR / "nai_sample.webp").read_bytes()
    assert parse_has_nai(data) is True
    assert parse_has_nai(b"\x89PNG\r\n\x1a\n") is False
