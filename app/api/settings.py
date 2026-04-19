from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.engine import get_session
from app.db.repository import get_setting, set_setting, get_all_settings
from app.llm.analyze import DEFAULT_SYSTEM_PROMPT
from app.llm.client import LLMClient
from app.llm.embedding import EmbeddingClient


class LLMSettings(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    prompt: str = ""


class EmbeddingSettings(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


def create_settings_router(engine) -> APIRouter:
    router = APIRouter()

    # --- LLM ---
    @router.get("/llm")
    async def get_llm_settings():
        with get_session(engine) as session:
            return LLMSettings(
                base_url=get_setting(session, "llm_base_url") or "",
                api_key=get_setting(session, "llm_api_key") or "",
                model=get_setting(session, "llm_model") or "",
                prompt=get_setting(session, "llm_prompt") or "",
            ).model_dump()

    @router.get("/llm/default-prompt")
    async def get_default_prompt():
        return {"prompt": DEFAULT_SYSTEM_PROMPT}

    @router.put("/llm")
    async def update_llm_settings(settings: LLMSettings):
        with get_session(engine) as session:
            set_setting(session, "llm_base_url", settings.base_url)
            set_setting(session, "llm_api_key", settings.api_key)
            set_setting(session, "llm_model", settings.model)
            set_setting(session, "llm_prompt", settings.prompt)
        return {"status": "saved"}

    @router.post("/llm/test")
    async def test_llm_connection(settings: LLMSettings):
        if not settings.base_url:
            return {"success": False, "error": "Base URL이 비어있습니다."}
        client = LLMClient(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
        )
        return await client.test_connection()

    # --- Embedding ---
    @router.get("/embedding")
    async def get_embedding_settings():
        with get_session(engine) as session:
            return EmbeddingSettings(
                base_url=get_setting(session, "embedding_base_url") or "",
                api_key=get_setting(session, "embedding_api_key") or "",
                model=get_setting(session, "embedding_model") or "",
            ).model_dump()

    @router.put("/embedding")
    async def update_embedding_settings(settings: EmbeddingSettings):
        with get_session(engine) as session:
            set_setting(session, "embedding_base_url", settings.base_url)
            set_setting(session, "embedding_api_key", settings.api_key)
            set_setting(session, "embedding_model", settings.model)
        return {"status": "saved"}

    @router.post("/embedding/test")
    async def test_embedding_connection(settings: EmbeddingSettings):
        if not settings.base_url:
            return {"success": False, "error": "Base URL이 비어있습니다."}
        client = EmbeddingClient(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
        )
        return await client.test_connection()

    return router
