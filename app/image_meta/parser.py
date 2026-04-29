"""NAI 메타데이터 검출. WebP/EXIF/UserComment/NAI 시그니처 매칭.

검증된 시그니처: EXIF UserComment 의 ASCII 텍스트가 JSON 으로 parse 되고,
최상위에 "Comment" 키가 있고, 그 값(string)을 다시 JSON parse 했을 때 "prompt" 키가 존재하면 NAI."""

from __future__ import annotations

import json
import struct


def parse_has_nai(buf: bytes) -> bool:
    return parse_nai_metadata(buf) is not None


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
        if tag == 0x8769:  # ExifIFDPointer
            (sub_off,) = struct.unpack(fmt + "I", vbytes)
            sub = _walk_ifd_for_user_comment(payload, sub_off, fmt)
            if sub is not None:
                return sub
        elif tag == 0x9286:  # UserComment
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


def parse_nai_metadata(buf: bytes) -> dict | None:
    exif = _extract_exif_chunk(buf)
    if exif is None:
        return None
    text = _extract_user_comment(exif)
    if text is None:
        return None
    return _to_metadata(text)


def _to_metadata(text: str) -> dict | None:
    try:
        outer = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(outer, dict):
        return None
    inner_str = outer.get("Comment")
    if not isinstance(inner_str, str):
        return None
    try:
        inner = json.loads(inner_str)
    except (ValueError, TypeError):
        return None
    if not isinstance(inner, dict) or "prompt" not in inner:
        return None
    return _convert_nai_format(inner)


def _convert_nai_format(inner: dict) -> dict:
    out: dict = {}

    if isinstance(inner.get("prompt"), str):
        out["prompt"] = inner["prompt"]

    negative = _extract_negative(inner)
    if negative:
        out["negative"] = negative

    _maybe_int(out, "steps", inner.get("steps"))
    _maybe_float(out, "cfg_scale", inner.get("scale"))
    _maybe_float(out, "cfg_rescale", inner.get("cfg_rescale"))
    _maybe_int(out, "seed", inner.get("seed"))
    _maybe_str(out, "sampler", inner.get("sampler"))
    _maybe_str(out, "scheduler", inner.get("noise_schedule"))
    _maybe_int(out, "width", inner.get("width"))
    _maybe_int(out, "height", inner.get("height"))

    chars = _extract_characters(inner)
    if chars:
        out["characters"] = chars

    out["source"] = "exif_user_comment"
    return out


def _extract_negative(inner: dict) -> str:
    v4_neg = inner.get("v4_negative_prompt")
    if isinstance(v4_neg, dict):
        cap = v4_neg.get("caption")
        if isinstance(cap, dict):
            base = cap.get("base_caption")
            if isinstance(base, str) and base:
                return base
    for key in ("uc", "negative_prompt", "undesired_content"):
        v = inner.get(key)
        if isinstance(v, str) and v:
            return v
    return ""


def _extract_characters(inner: dict) -> list[dict]:
    pos_caps = _char_captions(inner.get("v4_prompt"))
    neg_caps = _char_captions(inner.get("v4_negative_prompt"))
    n = max(len(pos_caps), len(neg_caps))
    if n == 0:
        return []
    return [
        {
            "prompt": pos_caps[i] if i < len(pos_caps) else "",
            "negative": neg_caps[i] if i < len(neg_caps) else "",
        }
        for i in range(n)
    ]


def _char_captions(v4_block) -> list[str]:
    if not isinstance(v4_block, dict):
        return []
    cap = v4_block.get("caption")
    if not isinstance(cap, dict):
        return []
    arr = cap.get("char_captions")
    if not isinstance(arr, list):
        return []
    out = []
    for c in arr:
        if isinstance(c, dict):
            cc = c.get("char_caption")
            out.append(cc if isinstance(cc, str) else "")
    return out


def _maybe_int(out: dict, key: str, v) -> None:
    if v is None:
        return
    try:
        out[key] = int(v)
    except (ValueError, TypeError):
        pass


def _maybe_float(out: dict, key: str, v) -> None:
    if v is None:
        return
    try:
        out[key] = float(v)
    except (ValueError, TypeError):
        pass


def _maybe_str(out: dict, key: str, v) -> None:
    if isinstance(v, str) and v:
        out[key] = v
