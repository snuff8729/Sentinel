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
from app.api.image_meta import create_image_meta_router
from app.api.saved import create_saved_router
from app.api.tags import create_tags_router
from app.saved.worker import SavedImageWorker
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


def _silence_proactor_connection_reset(loop, context):
    """Windows ProactorEventLoop에서 클라이언트가 먼저 끊을 때 발생하는 무해한 ConnectionResetError 무시.
    이미 응답은 정상 전송됐고, 소켓 shutdown() 단계에서 원격 RST를 만났을 뿐임."""
    exc = context.get("exception")
    msg = context.get("message", "")
    if isinstance(exc, ConnectionResetError) and "_call_connection_lost" in msg:
        return
    loop.default_exception_handler(context)


@app.on_event("startup")
async def startup():
    global worker
    asyncio.get_running_loop().set_exception_handler(_silence_proactor_connection_reset)
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

    # 좀비 청크 파일 정리 (재개 미지원)
    uploads_dir = Path(data_dir) / ".uploads"
    if uploads_dir.exists():
        for part in uploads_dir.glob("*.part"):
            try:
                part.unlink()
            except OSError:
                pass

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

    image_meta_router = create_image_meta_router(engine)
    app.include_router(image_meta_router, prefix="/api/image-meta")

    saved_signal = asyncio.Event()
    saved_worker = SavedImageWorker(engine=engine, data_dir=data_dir, signal=saved_signal)
    asyncio.create_task(saved_worker.run())

    saved_router = create_saved_router(engine=engine, data_dir=data_dir, worker_signal=saved_signal)
    app.include_router(saved_router, prefix="/api/saved-images")

    tags_router = create_tags_router(engine)
    app.include_router(tags_router, prefix="/api/tags")

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
