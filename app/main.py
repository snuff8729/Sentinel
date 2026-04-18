import asyncio

from fastapi import FastAPI

from app.api.backup import create_backup_router
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

    router = create_backup_router(worker, event_bus)
    app.include_router(router, prefix="/api/backup")

    asyncio.create_task(worker.run())


@app.get("/")
async def root():
    return {"message": "Hello from Sentinel"}


@app.get("/health")
async def health():
    return {"status": "ok"}
