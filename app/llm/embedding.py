from __future__ import annotations

import json
import logging
import math

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

    async def test_connection(self) -> dict:
        try:
            vec = await self.embed("test")
            return {"success": True, "dimensions": len(vec)}
        except Exception as e:
            return {"success": False, "error": str(e)}


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embedding_to_json(vec: list[float]) -> str:
    return json.dumps(vec)


def json_to_embedding(s: str) -> list[float]:
    return json.loads(s)
