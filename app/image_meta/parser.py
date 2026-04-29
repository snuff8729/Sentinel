"""NAI 메타데이터 검출. WebP/EXIF/UserComment/NAI 시그니처 매칭.

검증된 시그니처: EXIF UserComment 의 ASCII 텍스트가 JSON 으로 parse 되고,
최상위에 "Comment" 키가 있고, 그 값(string)을 다시 JSON parse 했을 때 "prompt" 키가 존재하면 NAI."""

from __future__ import annotations

import json
import struct


def parse_has_nai(buf: bytes) -> bool:
    exif = _extract_exif_chunk(buf)
    if exif is None:
        return False
    user_comment = _extract_user_comment(exif)
    if user_comment is None:
        return False
    return _is_nai_signature(user_comment)


def _extract_exif_chunk(buf: bytes) -> bytes | None:
    if len(buf) < 12 or buf[:4] != b"RIFF" or buf[8:12] != b"WEBP":
        return None
    i = 12
    while i + 8 <= len(buf):
        fourcc = buf[i : i + 4]
        (size,) = struct.unpack("<I", buf[i + 4 : i + 8])
        body_start = i + 8
        body_end = body_start + size
        if body_end > len(buf):
            return None
        if fourcc == b"EXIF":
            return buf[body_start:body_end]
        i = body_end + (size & 1)
    return None


def _extract_user_comment(exif: bytes) -> str | None:
    payload = exif[6:] if exif.startswith(b"Exif\x00\x00") else exif
    if len(payload) < 8:
        return None
    endian = payload[:2]
    if endian == b"II":
        fmt = "<"
    elif endian == b"MM":
        fmt = ">"
    else:
        return None
    try:
        (ifd_off,) = struct.unpack(fmt + "I", payload[4:8])
        return _walk_ifd_for_user_comment(payload, ifd_off, fmt)
    except struct.error:
        return None


def _walk_ifd_for_user_comment(payload: bytes, off: int, fmt: str) -> str | None:
    if off + 2 > len(payload):
        return None
    (n,) = struct.unpack(fmt + "H", payload[off : off + 2])
    for k in range(n):
        e = off + 2 + k * 12
        if e + 12 > len(payload):
            return None
        tag, type_, count = struct.unpack(fmt + "HHI", payload[e : e + 8])
        vbytes = payload[e + 8 : e + 12]
        if tag == 0x8769:
            (sub_off,) = struct.unpack(fmt + "I", vbytes)
            sub = _walk_ifd_for_user_comment(payload, sub_off, fmt)
            if sub is not None:
                return sub
        elif tag == 0x9286:
            return _decode_user_comment(payload, fmt, type_, count, vbytes)
    return None


def _decode_user_comment(payload: bytes, fmt: str, type_: int, count: int, vbytes: bytes) -> str | None:
    if type_ != 7:
        return None
    if count <= 4:
        data = vbytes[:count]
    else:
        (off,) = struct.unpack(fmt + "I", vbytes)
        if off + count > len(payload):
            return None
        data = payload[off : off + count]
    if len(data) < 8:
        return None
    prefix, body = data[:8], data[8:]
    if prefix.startswith(b"ASCII"):
        return body.decode("utf-8", "replace")
    if prefix.startswith(b"UNICODE"):
        return body.decode("utf-16", "replace")
    if prefix.startswith(b"JIS"):
        return None
    return body.decode("utf-8", "replace")


def _is_nai_signature(text: str) -> bool:
    try:
        outer = json.loads(text)
    except (ValueError, TypeError):
        return False
    if not isinstance(outer, dict):
        return False
    inner_str = outer.get("Comment")
    if not isinstance(inner_str, str):
        return False
    try:
        inner = json.loads(inner_str)
    except (ValueError, TypeError):
        return False
    return isinstance(inner, dict) and "prompt" in inner
