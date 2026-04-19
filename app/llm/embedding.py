from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """OpenAI 호환 Embedding API 클라이언트."""

    def __init__(self, base_url: str, api_key: str = "", model: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def embed(self, text: str) -> list[float]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "input": text,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """여러 텍스트를 한 번의 API 호출로 임베딩."""
        if not texts:
            return []
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            # 결과를 index 순서대로 정렬
            sorted_data = sorted(data["data"], key=lambda x: x["index"])
            return [d["embedding"] for d in sorted_data]

    async def test_connection(self) -> dict:
        try:
            vec = await self.embed("test")
            return {"success": True, "dimensions": len(vec)}
        except Exception as e:
            return {"success": False, "error": str(e)}


