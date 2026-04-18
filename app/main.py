import asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.backup import create_backup_router
from app.api.channel import create_channel_router
from app.backup.events import EventBus
from app.backup.service import BackupService
from app.backup.worker import BackupWorker
from app.db.engine import create_engine_and_tables
from app.scraper.arca.client import ArcaClient

app = FastAPI(title="Sentinel")

worker: BackupWorker | None = None


@app.on_event("startup")
async def startup():
    global worker
    engine = create_engine_and_tables()
    client = ArcaClient()
    event_bus = EventBus()
    service = BackupService(engine=engine, client=client)
    worker = BackupWorker(service=service, event_bus=event_bus)

    # API routers
    channel_router = create_channel_router(client)
    app.include_router(channel_router, prefix="/api/channel")
    app.include_router(channel_router.article_router, prefix="/api/article")

    backup_router = create_backup_router(worker, event_bus, engine)
    app.include_router(backup_router, prefix="/api/backup")

    asyncio.create_task(worker.run())

    # Static file serving (React build)
    dist_dir = Path(__file__).parent.parent / "web" / "dist"
    if dist_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

        @app.get("/{path:path}")
        async def spa_fallback(request: Request, path: str):
            # Serve actual files if they exist, otherwise index.html for SPA routing
            file = dist_dir / path
            if file.is_file():
                return FileResponse(file)
            return FileResponse(dist_dir / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
