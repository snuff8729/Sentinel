from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.engine import get_session
from app.db.repository import follow_user, unfollow_user, get_followed_users, get_followed_usernames


class FollowRequest(BaseModel):
    username: str
    note: str | None = None


def create_follow_router(engine) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def list_followed():
        with get_session(engine) as session:
            users = get_followed_users(session)
            return [{"username": u.username, "note": u.note} for u in users]

    @router.get("/usernames")
    async def list_followed_usernames():
        with get_session(engine) as session:
            return list(get_followed_usernames(session))

    @router.post("/")
    async def add_follow(req: FollowRequest):
        with get_session(engine) as session:
            follow_user(session, req.username, req.note)
        return {"status": "followed", "username": req.username}

    @router.delete("/{username}")
    async def remove_follow(username: str):
        with get_session(engine) as session:
            unfollow_user(session, username)
        return {"status": "unfollowed", "username": username}

    return router
