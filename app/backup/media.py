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
    warning: str | None = None  # placeholder 등 경고 메시지

def extract_backup_html(html: str) -> str:
    """전체 HTML에서 본문 + 댓글 영역만 추출하여 깔끔한 HTML로 반환."""
    soup = BeautifulSoup(html, "lxml")

    # 본문 헤더 (제목, 작성자, 추천 등)
    head = soup.select_one(".article-head")
    # 본문 내용
    content = soup.select_one(".article-body")
    # 댓글
    comments = soup.select_one("#comment, .article-comment")

    # 댓글 쓰기 폼/버튼/글쓰기 링크/아바타 제거
    if comments:
        for el in comments.select("form, .btn-arca-article-write, .reply-form, .avatar"):
            el.decompose()

    parts = []
    parts.append('<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>')
    if head:
        parts.append(str(head))
    if content:
        parts.append(str(content))
    if comments:
        parts.append(str(comments))
    parts.append("</body></html>")

    return "\n".join(parts)


def extract_media_from_html(html: str, article_id: int) -> list[MediaItem]:
    soup = BeautifulSoup(html, "lxml")

    # 본문 + 댓글 영역에서만 미디어 추출
    search_areas = []
    content = soup.select_one(".article-body")
    if content:
        search_areas.append(content)
    comments = soup.select_one("#comment, .article-comment")
    if comments:
        search_areas.append(comments)

    items: list[MediaItem] = []
    seen_urls: set[str] = set()

    all_imgs = []
    all_vids = []
    all_auds = []
    for area in search_areas:
        all_imgs.extend(area.select("img"))
        all_vids.extend(area.select("video source, video[src]"))
        all_auds.extend(area.select("audio[src], audio source"))

    for img in all_imgs:
        src = img.get("src", "")
        if not src:
            continue
        # 아바타 이미지 제외
        parent = img.parent
        if parent and "avatar" in " ".join(parent.get("class", [])):
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
            warning = _check_placeholder(url)
            filename = _get_filename(url)
            file_type = _classify_ext(_get_ext(url))
            subdir = _subdir_for_type(file_type)
            local_path = f"articles/{article_id}/{subdir}/{filename}"
            relative_path = f"./{subdir}/{filename}"
            items.append(MediaItem(url=url, local_path=local_path, file_type=file_type, relative_path=relative_path, warning=warning))

    for vid in all_vids:
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

    for aud in all_auds:
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

PLACEHOLDER_PATTERNS = {"blocked.png", "deleted.png", "noimage.png"}


def _check_placeholder(url: str) -> str | None:
    filename = PurePosixPath(urlparse(url).path).name
    if filename in PLACEHOLDER_PATTERNS:
        return f"arca.live placeholder image ({filename})"
    return None


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
