import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from sqlmodel import Session, select

from app.db.engine import create_engine_and_tables
from app.db.models import SavedImage
from app.saved.worker import SavedImageWorker


def _make_worker(tmp_path):
    engine = create_engine_and_tables("sqlite:///:memory:")
    signal = asyncio.Event()
    worker = SavedImageWorker(engine=engine, data_dir=str(tmp_path), signal=signal)
    return worker, engine, signal


def _seed_pending(engine, src_url="https://ac-p3.namu.la/x/abc.png", article_id=42, hex_id="abc"):
    with Session(engine) as s:
        row = SavedImage(
            article_id=article_id,
            hex=hex_id,
            src_url=src_url,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id


def test_worker_processes_pending_to_completed(tmp_path):
    worker, engine, _ = _make_worker(tmp_path)
    row_id = _seed_pending(engine)

    with patch("app.saved.worker.fetch_full_image", return_value=b"\x89PNG\r\n\x1a\nfake"), \
         patch("app.saved.worker.parse_nai_metadata", return_value=None):
        async def run_once():
            row = await asyncio.to_thread(worker._claim_next_pending)
            await worker._process(row)
        asyncio.run(run_once())

    with Session(engine) as s:
        row = s.get(SavedImage, row_id)
    assert row.status == "completed"
    assert row.file_path == "saved/42/abc.png"
    assert row.payload_json is None
    assert row.completed_at is not None
    assert (tmp_path / "saved" / "42" / "abc.png").exists()


def test_worker_writes_metadata_when_nai(tmp_path):
    worker, engine, _ = _make_worker(tmp_path)
    row_id = _seed_pending(engine)
    metadata = {"prompt": "p", "steps": 28, "source": "exif_user_comment"}

    with patch("app.saved.worker.fetch_full_image", return_value=b"\x89PNG\r\n\x1a\nfake"), \
         patch("app.saved.worker.parse_nai_metadata", return_value=metadata):
        async def run_once():
            row = await asyncio.to_thread(worker._claim_next_pending)
            await worker._process(row)
        asyncio.run(run_once())

    with Session(engine) as s:
        row = s.get(SavedImage, row_id)
    assert row.status == "completed"
    import json as _j
    assert _j.loads(row.payload_json) == metadata
    assert (tmp_path / "saved" / "42" / "abc.json").exists()


def test_worker_retries_on_transient_failure(tmp_path):
    worker, engine, _ = _make_worker(tmp_path)
    row_id = _seed_pending(engine)
    call_count = {"n": 0}

    def fake_fetch(url):
        call_count["n"] += 1
        if call_count["n"] < 2:
            return None
        return b"\x89PNG\r\n\x1a\nfake"

    async def run_until_done():
        row = await asyncio.to_thread(worker._claim_next_pending)
        with patch("app.saved.worker.fetch_full_image", side_effect=fake_fetch), \
             patch("app.saved.worker.parse_nai_metadata", return_value=None), \
             patch("asyncio.sleep", return_value=None):
            await worker._process(row)
            row2 = await asyncio.to_thread(worker._claim_next_pending)
            assert row2 is not None  # row was reset to pending
            await worker._process(row2)
    asyncio.run(run_until_done())

    with Session(engine) as s:
        row = s.get(SavedImage, row_id)
    assert row.status == "completed"
    assert row.retry_count == 1


def test_worker_marks_failed_after_three_retries(tmp_path):
    worker, engine, _ = _make_worker(tmp_path)
    row_id = _seed_pending(engine)

    async def run_until_done():
        with patch("app.saved.worker.fetch_full_image", return_value=None), \
             patch("asyncio.sleep", return_value=None):
            for _ in range(4):
                row = await asyncio.to_thread(worker._claim_next_pending)
                if row is None:
                    break
                await worker._process(row)
    asyncio.run(run_until_done())

    with Session(engine) as s:
        row = s.get(SavedImage, row_id)
    assert row.status == "failed"
    assert row.retry_count == 3
    assert row.error is not None


def test_worker_resets_zombies_on_startup(tmp_path):
    worker, engine, _ = _make_worker(tmp_path)
    with Session(engine) as s:
        s.add(SavedImage(
            article_id=42, hex="zombie", src_url="https://ac.namu.la/x.png",
            status="in_progress", created_at=datetime.now(timezone.utc),
        ))
        s.commit()

    asyncio.run(asyncio.to_thread(worker._reset_zombies))

    with Session(engine) as s:
        row = s.exec(select(SavedImage).where(SavedImage.hex == "zombie")).first()
    assert row.status == "pending"
