from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from sqlmodel import select

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
            old_model = get_setting(session, "embedding_model") or ""
            set_setting(session, "embedding_base_url", settings.base_url)
            set_setting(session, "embedding_api_key", settings.api_key)
            set_setting(session, "embedding_model", settings.model)

            model_changed = old_model != settings.model and old_model != ""
            if model_changed:
                set_setting(session, "embedding_stale", "true")

        return {"status": "saved", "model_changed": model_changed}

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

    @router.get("/embedding/status")
    async def get_embedding_status():
        from sqlalchemy import text
        with get_session(engine) as session:
            stale = get_setting(session, "embedding_stale") == "true"
            try:
                count = session.execute(text("SELECT COUNT(*) FROM article_vec")).scalar()
            except Exception:
                count = 0
            total_articles = session.execute(text("SELECT COUNT(*) FROM article WHERE backup_status = 'completed'")).scalar()
        return {
            "stale": stale,
            "embedded_count": count,
            "total_articles": total_articles,
        }

    @router.post("/embedding/recalculate")
    async def recalculate_embeddings():
        import asyncio
        from sqlalchemy import text
        from app.llm.version import VersionDetector

        with get_session(engine) as session:
            base_url = get_setting(session, "embedding_base_url")
            if not base_url:
                return {"error": "임베딩이 설정되지 않았습니다."}
            # 기존 벡터 테이블 드롭
            try:
                session.execute(text("DROP TABLE IF EXISTS article_vec"))
                session.commit()
            except Exception:
                pass
            set_setting(session, "embedding_stale", "false")

        detector = VersionDetector(engine=engine)

        # 완료된 게시글 목록
        from app.db.models import Article
        with get_session(engine) as session:
            articles = session.exec(select(Article).where(Article.backup_status == "completed")).all()
            article_ids = [a.id for a in articles]

        success = 0
        failed = 0
        for aid in article_ids:
            try:
                if await detector.generate_embedding(aid):
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        return {"success": success, "failed": failed, "total": len(article_ids)}

    return router
