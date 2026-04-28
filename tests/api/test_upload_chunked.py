from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.backup import create_backup_router
from app.backup.events import EventBus
from app.backup.worker import BackupWorker
from app.db.engine import create_engine_and_tables
from app.db.models import Article


@pytest.fixture
def setup(tmp_path):
    """real engine + tmp data_dir 로 실제 파일/DB 동작 검증."""
    db_path = tmp_path / "test.db"
    engine = create_engine_and_tables(f"sqlite:///{db_path}")

    with Session(engine) as session:
        article = Article(
            id=1,
            channel_slug="test",
            title="t",
            author="",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            url="http://example.com/1",
        )
        session.add(article)
        session.commit()

    service = MagicMock()
    service._data_dir = str(tmp_path)
    service._engine = engine
    event_bus = EventBus()
    worker = BackupWorker(service=service, event_bus=event_bus)

    test_app = FastAPI()
    router = create_backup_router(worker, event_bus, engine=engine)
    test_app.include_router(router, prefix="/api/backup")
    client = TestClient(test_app)
    return client, tmp_path, engine


def test_init_returns_upload_id_and_creates_uploads_dir(setup):
    client, tmp_path, _ = setup
    resp = client.post("/api/backup/upload-free/init", json={
        "article_id": 1,
        "filename": "hello.txt",
        "total_size": 5,
        "total_chunks": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "upload_id" in data
    assert (tmp_path / ".uploads").is_dir()


def test_init_rejects_total_chunks_mismatch(setup):
    client, _, _ = setup
    # 25MB → 10MB 청크 3개여야 함, 2 로 보내면 거부
    resp = client.post("/api/backup/upload-free/init", json={
        "article_id": 1,
        "filename": "x.bin",
        "total_size": 25 * 1024 * 1024,
        "total_chunks": 2,
    })
    assert resp.status_code == 400


def test_init_rejects_oversized_file(setup):
    client, _, _ = setup
    resp = client.post("/api/backup/upload-free/init", json={
        "article_id": 1,
        "filename": "huge.bin",
        "total_size": 11 * 1024 * 1024 * 1024,  # 11GB > 10GB cap
        "total_chunks": 1126,
    })
    assert resp.status_code == 413


def _init_upload(client, *, article_id=1, filename="x.bin", total_size, total_chunks, note=None):
    resp = client.post("/api/backup/upload-free/init", json={
        "article_id": article_id,
        "filename": filename,
        "total_size": total_size,
        "total_chunks": total_chunks,
        "note": note,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["upload_id"]


def test_chunk_appends_to_temp_file(setup):
    client, tmp_path, _ = setup
    payload = b"hello world"
    upload_id = _init_upload(client, total_size=len(payload), total_chunks=1)

    resp = client.post(
        f"/api/backup/upload-free/chunk/{upload_id}?index=0",
        files={"chunk": ("c0", payload, "application/octet-stream")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"received": 1, "total": 1}
    assert (tmp_path / ".uploads" / f"{upload_id}.part").read_bytes() == payload


def test_chunk_out_of_order_rejected(setup):
    client, _, _ = setup
    upload_id = _init_upload(client, total_size=20 * 1024 * 1024, total_chunks=2)

    resp = client.post(
        f"/api/backup/upload-free/chunk/{upload_id}?index=1",
        files={"chunk": ("c1", b"x" * (10 * 1024 * 1024), "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_chunk_unknown_upload_id(setup):
    client, _, _ = setup
    fake = "00000000-0000-0000-0000-000000000000"
    resp = client.post(
        f"/api/backup/upload-free/chunk/{fake}?index=0",
        files={"chunk": ("c0", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 404


def test_chunk_invalid_upload_id_format(setup):
    client, _, _ = setup
    resp = client.post(
        "/api/backup/upload-free/chunk/not-a-uuid?index=0",
        files={"chunk": ("c0", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_non_final_chunk_must_be_exact_size(setup):
    client, _, _ = setup
    upload_id = _init_upload(client, total_size=20 * 1024 * 1024, total_chunks=2)

    resp = client.post(
        f"/api/backup/upload-free/chunk/{upload_id}?index=0",
        files={"chunk": ("c0", b"x" * 1024, "application/octet-stream")},
    )
    assert resp.status_code == 400


from app.db.models import ArticleFile


def _send_chunk(client, upload_id, index, data):
    resp = client.post(
        f"/api/backup/upload-free/chunk/{upload_id}?index={index}",
        files={"chunk": (f"c{index}", data, "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text


def test_complete_moves_file_and_creates_db_row(setup):
    client, tmp_path, engine = setup
    payload = b"final content"
    upload_id = _init_upload(client, filename="report.txt", total_size=len(payload), total_chunks=1, note="memo")
    _send_chunk(client, upload_id, 0, payload)

    resp = client.post(f"/api/backup/upload-free/complete/{upload_id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["filename"] == "report.txt"

    final_path = tmp_path / "articles" / "1" / "downloads" / "report.txt"
    assert final_path.read_bytes() == payload
    assert not (tmp_path / ".uploads" / f"{upload_id}.part").exists()

    with Session(engine) as session:
        rows = session.query(ArticleFile).filter_by(article_id=1).all()
        assert len(rows) == 1
        assert rows[0].filename == "report.txt"
        assert rows[0].size == len(payload)
        assert rows[0].note == "memo"


def test_complete_before_all_chunks_rejected(setup):
    client, tmp_path, _ = setup
    upload_id = _init_upload(client, total_size=20 * 1024 * 1024, total_chunks=2)
    _send_chunk(client, upload_id, 0, b"x" * (10 * 1024 * 1024))

    resp = client.post(f"/api/backup/upload-free/complete/{upload_id}")
    assert resp.status_code == 400
    assert not (tmp_path / ".uploads" / f"{upload_id}.part").exists()  # cleaned up


def test_complete_size_mismatch_rejected(setup, monkeypatch):
    client, tmp_path, _ = setup
    payload = b"abc"
    upload_id = _init_upload(client, total_size=len(payload), total_chunks=1)
    _send_chunk(client, upload_id, 0, payload)

    # tamper temp file to wrong size
    temp = tmp_path / ".uploads" / f"{upload_id}.part"
    temp.write_bytes(b"abcdef")

    resp = client.post(f"/api/backup/upload-free/complete/{upload_id}")
    assert resp.status_code == 400


def test_complete_filename_traversal_blocked(setup):
    client, tmp_path, _ = setup
    payload = b"x"
    # filename with traversal attempt — _normalize_filename strips path components
    upload_id = _init_upload(client, filename="../../etc/passwd", total_size=1, total_chunks=1)
    _send_chunk(client, upload_id, 0, payload)

    resp = client.post(f"/api/backup/upload-free/complete/{upload_id}")
    # 정규화로 "passwd" 가 되어 articles/1/downloads/passwd 로 저장됨 (data_dir 내부)
    assert resp.status_code == 200
    final = tmp_path / "articles" / "1" / "downloads" / "passwd"
    assert final.exists()


def test_abort_removes_temp_and_meta(setup):
    client, tmp_path, _ = setup
    payload = b"partial"
    upload_id = _init_upload(client, total_size=len(payload), total_chunks=1)
    _send_chunk(client, upload_id, 0, payload)
    temp = tmp_path / ".uploads" / f"{upload_id}.part"
    assert temp.exists()

    resp = client.delete(f"/api/backup/upload-free/{upload_id}")
    assert resp.status_code == 200
    assert resp.json() == {"aborted": True}
    assert not temp.exists()


def test_abort_unknown_upload_id_idempotent(setup):
    client, _, _ = setup
    fake = "00000000-0000-0000-0000-000000000000"
    resp = client.delete(f"/api/backup/upload-free/{fake}")
    assert resp.status_code == 200
    assert resp.json() == {"aborted": True}


def test_abort_invalid_upload_id_format(setup):
    client, _, _ = setup
    resp = client.delete("/api/backup/upload-free/not-a-uuid")
    assert resp.status_code == 400
