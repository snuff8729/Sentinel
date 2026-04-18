from __future__ import annotations

import httpx
import logging

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI 호환 API 클라이언트."""

    def __init__(self, base_url: str, api_key: str = "", model: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def chat(self, system_prompt: str, user_message: str) -> str:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def test_connection(self) -> dict:
        """연결 테스트. 성공하면 모델 정보 반환."""
        try:
            result = await self.chat(
                system_prompt="You are a test assistant.",
                user_message="Say 'ok' and nothing else.",
            )
            return {"success": True, "response": result.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}
