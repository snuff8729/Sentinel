"""외부 다운로드 링크에서 파일을 받는 모듈.

지원:
- Realm (realm.risuai.net): API로 직접 다운로드
- Proton Drive: E2EE라 자동 다운로드 불가 — 링크만 제공

향후 추가 가능:
- chub.ai
- catbox
- Google Drive
- MEGA
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class ExternalDownloader:
    def __init__(self, data_dir: str = "data"):
        self._data_dir = Path(data_dir)

    async def download(self, url: str, article_id: int) -> dict:
        """URL에서 파일을 다운로드.

        Returns: {
            "success": bool,
            "local_path": str | None,
            "filename": str | None,
            "size": int,
            "error": str | None,
            "manual_required": bool,  # 사용자가 직접 다운로드해야 함
        }
        """
        domain = urlparse(url).netloc.lower()

        if "realm.risuai.net" in domain:
            return await self._download_realm(url, article_id)
        elif "drive.proton.me" in domain:
            return self._proton_manual(url)
        elif "chub.ai" in domain:
            return {"success": False, "local_path": None, "filename": None, "size": 0,
                    "error": "chub.ai 자동 다운로드 미지원", "manual_required": True}
        else:
            return {"success": False, "local_path": None, "filename": None, "size": 0,
                    "error": f"미지원 도메인: {domain}", "manual_required": True}

    async def _download_realm(self, url: str, article_id: int) -> dict:
        """Realm 캐릭터 다운로드. /api/v1/download/charx-v3/{id}"""
        # URL에서 character ID 추출
        match = re.search(r"character/([a-f0-9-]+)", url)
        if not match:
            return {"success": False, "local_path": None, "filename": None, "size": 0,
                    "error": "Realm character ID 추출 실패", "manual_required": True}

        char_id = match.group(1)
        download_url = f"https://realm.risuai.net/api/v1/download/charx-v3/{char_id}"

        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                # 페이지에서 캐릭터 이름 가져오기
                char_name = char_id
                try:
                    from bs4 import BeautifulSoup
                    page_resp = await client.get(f"https://realm.risuai.net/character/{char_id}", timeout=10)
                    if page_resp.status_code == 200:
                        soup = BeautifulSoup(page_resp.text, "lxml")
                        title = soup.select_one("title")
                        if title:
                            # "RisuRealm - CharName" → "CharName"
                            t = title.get_text(strip=True)
                            if " - " in t:
                                char_name = t.split(" - ", 1)[1].strip()
                            elif t:
                                char_name = t
                except Exception:
                    pass

                resp = await client.get(download_url)
                resp.raise_for_status()

                # 파일명 결정
                content_disp = resp.headers.get("content-disposition", "")
                if "filename=" in content_disp:
                    fn = re.search(r'filename="?([^";\s]+)"?', content_disp)
                    filename = fn.group(1) if fn else f"{char_name}.charx"
                else:
                    # 안전한 파일명으로 변환
                    safe_name = re.sub(r'[\\/:*?"<>|]', '_', char_name)
                    content_type = resp.headers.get("content-type", "")
                    if "charx" in content_type:
                        filename = f"{safe_name}.charx"
                    elif "json" in content_type:
                        filename = f"{safe_name}.json"
                    else:
                        filename = f"{safe_name}.bin"

                # 저장
                save_dir = self._data_dir / "articles" / str(article_id) / "downloads"
                save_dir.mkdir(parents=True, exist_ok=True)
                save_path = save_dir / filename
                save_path.write_bytes(resp.content)

                local_path = f"articles/{article_id}/downloads/{filename}"
                logger.info("[%d] Realm 다운로드 완료: %s (%.1fKB)", article_id, filename, len(resp.content) / 1024)

                return {
                    "success": True,
                    "local_path": local_path,
                    "filename": filename,
                    "size": len(resp.content),
                    "error": None,
                    "manual_required": False,
                }

        except Exception as e:
            logger.warning("[%d] Realm 다운로드 실패: %s", article_id, e)
            return {"success": False, "local_path": None, "filename": None, "size": 0,
                    "error": str(e), "manual_required": False}

    def _proton_manual(self, url: str) -> dict:
        """Proton Drive는 E2EE라 자동 다운로드 불가."""
        return {
            "success": False,
            "local_path": None,
            "filename": None,
            "size": 0,
            "error": "Proton Drive는 E2E 암호화로 자동 다운로드가 불가합니다. 브라우저에서 직접 다운로드해주세요.",
            "manual_required": True,
        }
