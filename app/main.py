import asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.backup import create_backup_router
from app.api.channel import create_channel_router
from app.api.follow import create_follow_router
from app.api.version import create_version_router
from app.api.settings import create_settings_router
from app.backup.events import EventBus
from app.backup.service import BackupService
from app.backup.worker import BackupWorker
from app.db.engine import create_engine_and_tables
from app.backup.downloader import ExternalDownloader
from app.llm.service import LinkAnalysisService
from app.llm.version import VersionDetector
from app.scraper.arca.client import ArcaClient

app = FastAPI(title="Sentinel")

worker: BackupWorker | None = None


@app.on_event("startup")
async def startup():
    global worker
    engine = create_engine_and_tables()
    client = ArcaClient()
    event_bus = EventBus()

    # 데이터 경로 로드
    from app.db.engine import get_session
    from app.db.repository import get_setting
    with get_session(engine) as session:
        data_dir = get_setting(session, "data_dir") or "data"

    service = BackupService(engine=engine, client=client, data_dir=data_dir)
    link_analysis = LinkAnalysisService(engine=engine, arca_client=client)
    version_detector = VersionDetector(engine=engine)
    downloader = ExternalDownloader(data_dir=data_dir)
    worker = BackupWorker(service=service, event_bus=event_bus, link_analysis=link_analysis, version_detector=version_detector, downloader=downloader)

    # API routers
    channel_router = create_channel_router(client, engine)
    app.include_router(channel_router, prefix="/api/channel")
    app.include_router(channel_router.article_router, prefix="/api/article")

    backup_router = create_backup_router(worker, event_bus, engine)
    app.include_router(backup_router, prefix="/api/backup")

    settings_router = create_settings_router(engine)
    app.include_router(settings_router, prefix="/api/settings")

    follow_router = create_follow_router(engine)
    app.include_router(follow_router, prefix="/api/follow")

    version_router = create_version_router(engine)
    app.include_router(version_router, prefix="/api/versions")

    asyncio.create_task(worker.run())

    # 백업 파일 정적 서빙 (이미지/비디오/오디오)
    data_path = Path(data_dir)
    if data_path.exists():
        app.mount("/data", StaticFiles(directory=str(data_path)), name="data")

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
