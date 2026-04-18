from __future__ import annotations
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse
from bs4 import BeautifulSoup

VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi"}
AUDIO_EXTS = {".mp3", ".ogg", ".wav", ".flac", ".m4a"}

@dataclass
class MediaItem:
    url: str
    local_path: str
    file_type: str
    relative_path: str

def extract_media_from_html(html: str, article_id: int) -> list[MediaItem]:
    soup = BeautifulSoup(html, "lxml")
    items: list[MediaItem] = []
    seen_urls: set[str] = set()

    for img in soup.select("img"):
        src = img.get("src", "")
        if not src:
            continue
        url = _normalize_url(src)
        url_key = _url_path_key(url)
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)
        if "arca-emoticon" in img.get("class", []):
            data_id = img.get("data-store-id", "") or img.get("data-id", "")
            if not data_id:
                # fallback: URL의 파일명 해시를 ID로 사용
                data_id = PurePosixPath(urlparse(url).path).stem
            ext = _get_ext(url)
            local_path = f"emoticons/{data_id}{ext}"
            relative_path = f"../../emoticons/{data_id}{ext}"
            items.append(MediaItem(url=url, local_path=local_path, file_type="emoticon", relative_path=relative_path))
        else:
            filename = _get_filename(url)
            file_type = _classify_ext(_get_ext(url))
            subdir = _subdir_for_type(file_type)
            local_path = f"articles/{article_id}/{subdir}/{filename}"
            relative_path = f"./{subdir}/{filename}"
            items.append(MediaItem(url=url, local_path=local_path, file_type=file_type, relative_path=relative_path))

    for vid in soup.select("video source, video[src]"):
        src = vid.get("src", "")
        if not src:
            continue
        url = _normalize_url(src)
        url_key = _url_path_key(url)
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)
        filename = _get_filename(url)
        local_path = f"articles/{article_id}/videos/{filename}"
        relative_path = f"./videos/{filename}"
        items.append(MediaItem(url=url, local_path=local_path, file_type="video", relative_path=relative_path))

    for aud in soup.select("audio[src], audio source"):
        src = aud.get("src", "")
        if not src:
            continue
        url = _normalize_url(src)
        url_key = _url_path_key(url)
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)
        filename = _get_filename(url)
        local_path = f"articles/{article_id}/audio/{filename}"
        relative_path = f"./audio/{filename}"
        items.append(MediaItem(url=url, local_path=local_path, file_type="audio", relative_path=relative_path))

    return items

def replace_urls_in_html(html: str, url_map: dict[str, str]) -> str:
    for original_url, local_path in url_map.items():
        parsed = urlparse(original_url)
        src_variant = f"//{parsed.netloc}{parsed.path}"
        if parsed.query:
            src_variant += f"?{parsed.query}"
        html = html.replace(src_variant, local_path)
        html = html.replace(src_variant.replace("&", "&amp;"), local_path)
        html = html.replace(original_url, local_path)
    return html

def _url_path_key(url: str) -> str:
    """Return a deduplication key based on path only (ignoring query params)."""
    parsed = urlparse(url)
    return f"{parsed.netloc}{parsed.path}"

def _normalize_url(src: str) -> str:
    if src.startswith("//"):
        return f"https:{src}"
    return src

def _get_ext(url: str) -> str:
    return PurePosixPath(urlparse(url).path).suffix

def _get_filename(url: str) -> str:
    return PurePosixPath(urlparse(url).path).name

def _classify_ext(ext: str) -> str:
    ext_lower = ext.lower()
    if ext_lower in VIDEO_EXTS:
        return "video"
    if ext_lower in AUDIO_EXTS:
        return "audio"
    return "image"

def _subdir_for_type(file_type: str) -> str:
    if file_type == "video":
        return "videos"
    if file_type == "audio":
        return "audio"
    return "images"
