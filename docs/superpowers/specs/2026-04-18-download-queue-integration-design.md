# 다운로드 큐 연동 설계

## 목적

다운로드 큐를 BackupService에 연동하여 도메인별 딜레이/동시실행을 적용하고, 백그라운드 워커로 서버를 블로킹하지 않으며, SSE로 실시간 진행도를 제공한다.

## 아키텍처

```
FastAPI 서버
  ├─ REST API
  │   POST /backup/{article_id}      → 큐에 추가, 즉시 응답
  │   DELETE /backup/{article_id}    → 특정 게시글 취소
  │   POST /backup/pause             → 일시정지
  │   POST /backup/resume            → 재개
  │   GET /backup/queue              → 현재 큐 상태
  │
  ├─ SSE
  │   GET /backup/events             → 실시간 이벤트 스트림
  │
  └─ BackupWorker (서버 시작 시 백그라운드 태스크)
       ├─ 게시글 큐: asyncio.Queue (순차 처리)
       ├─ 일시정지 제어: asyncio.Event
       └─ 현재 게시글 처리 중
            └─ DownloadQueue (도메인별 딜레이/동시실행)
```

## 파일 구조

```
app/
  backup/
    __init__.py
    media.py          # 변경 없음
    queue.py          # 기존 DownloadQueue — pause_event/cancelled 체크 추가
    service.py        # BackupService — DownloadQueue를 통해 다운로드하도록 수정
    worker.py         # NEW: BackupWorker (게시글 큐 + 일시정지/취소 제어)
    events.py         # NEW: EventBus (SSE 이벤트 발행/구독)
  api/
    __init__.py
    backup.py         # NEW: REST + SSE 엔드포인트
```

## BackupWorker (worker.py)

게시글 단위의 작업 큐를 관리. 서버 시작 시 백그라운드 asyncio 태스크로 실행.

### 상태

- `_queue: asyncio.Queue` — 대기 중인 게시글 요청 (article_id, channel_slug)
- `_pause_event: asyncio.Event` — set=실행중, clear=일시정지
- `_cancelled: set[int]` — 취소 요청된 article_id 집합
- `_current_article_id: int | None` — 현재 처리 중인 게시글 ID
- `_pending_ids: list[int]` — 큐에 대기 중인 게시글 ID 목록 (조회용)

### 메서드

```python
class BackupWorker:
    async def run()                    # 무한 루프 — 큐에서 꺼내서 처리
    async def enqueue(article_id, channel_slug)  # 큐에 추가
    def pause()                        # _pause_event.clear()
    def resume()                       # _pause_event.set()
    def cancel(article_id)             # _cancelled에 추가 + 큐에서 제거
    def get_status() -> WorkerStatus   # 현재 상태 반환
```

### 처리 흐름

```
run() 루프:
  1. _queue.get() → (article_id, channel_slug)
  2. cancelled 체크 → 맞으면 스킵
  3. _pause_event.wait() → 일시정지 상태면 대기
  4. EventBus에 article_started 발행
  5. BackupService.backup_article() 호출
     - service 내부에서 파일마다 pause_event.wait() + cancelled 체크
  6. 완료 후 EventBus에 article_completed 발행
  7. 다음 게시글로
```

### 일시정지 동작

1. `pause()` 호출 → `_pause_event.clear()`
2. 현재 다운로드 중인 파일은 끝까지 완료
3. 다음 파일 다운로드 전 `_pause_event.wait()`에서 대기
4. `resume()` 호출 → `_pause_event.set()` → 이어서 진행
5. EventBus에 `worker_paused` / `worker_resumed` 발행

### 취소 동작

1. `cancel(article_id)` 호출
2. 큐에 대기 중이면 `_pending_ids`에서 제거, `_cancelled`에 추가
3. 현재 처리 중이면 `_cancelled`에 추가 → 다음 파일 전에 체크하여 중단
4. 이미 다운로드된 파일은 보존
5. DB에서 `Article.backup_status = "cancelled"` 로 업데이트
6. EventBus에 `queue_updated` 발행

## DownloadQueue 수정 (queue.py)

기존 DownloadQueue에 pause/cancel 연동 추가.

### submit 변경

```python
async def submit(
    self,
    url: str,
    dest: str,
    download_fn: Callable[[str, str], Awaitable[None]],
    *,
    pause_event: asyncio.Event | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> None:
```

- `pause_event`: 파일 다운로드 시작 전 `await pause_event.wait()`
- `cancel_check`: 파일 다운로드 시작 전 `if cancel_check(): raise CancelledError`

## BackupService 수정 (service.py)

### _download_media 변경

기존 for 루프 직접 호출 → DownloadQueue.submit()으로 변경.

```python
async def _download_media(self, article_id, media, pause_event, cancel_check):
    for item in media:
        await self._queue.submit(
            url=item.url,
            dest=str(self._data_dir / item.local_path),
            download_fn=self._download_file,
            pause_event=pause_event,
            cancel_check=cancel_check,
        )
    await self._queue.wait_all()
```

### backup_article 시그니처 변경

```python
async def backup_article(
    self,
    article_id: int,
    channel_slug: str,
    *,
    force: bool = False,
    pause_event: asyncio.Event | None = None,
    cancel_check: Callable[[], bool] | None = None,
    event_bus: EventBus | None = None,
)
```

- `pause_event`, `cancel_check`: 워커에서 전달받아 큐에 주입
- `event_bus`: 파일 완료/실패 시 이벤트 발행

## EventBus (events.py)

SSE 이벤트 발행/구독을 위한 간단한 pub-sub.

```python
@dataclass
class Event:
    type: str           # "queue_updated", "article_started" 등
    data: dict          # JSON 직렬화 가능한 데이터

class EventBus:
    async def publish(event: Event)        # 모든 구독자에게 전달
    def subscribe() -> asyncio.Queue       # 새 구독자 등록, Queue 반환
    def unsubscribe(queue: asyncio.Queue)  # 구독 해제
```

### SSE 이벤트 목록

| 이벤트 | data 내용 |
|--------|-----------|
| `queue_updated` | `{"queue": [{"article_id": 100, "title": "...", "status": "pending"}, ...]}` |
| `article_started` | `{"article_id": 100, "title": "...", "total_files": 73}` |
| `file_completed` | `{"article_id": 100, "filename": "abc.png", "size_kb": 45.2, "current": 5, "total": 73, "file_type": "image"}` |
| `file_failed` | `{"article_id": 100, "filename": "xyz.mp4", "error": "HTTP 404"}` |
| `article_completed` | `{"article_id": 100, "success_count": 70, "fail_count": 3}` |
| `worker_paused` | `{}` |
| `worker_resumed` | `{}` |

## API 엔드포인트 (api/backup.py)

### REST

```
POST   /api/backup/{channel_slug}/{article_id}
  → worker.enqueue(article_id, channel_slug)
  → 응답: {"status": "queued", "position": 3}

DELETE /api/backup/{article_id}
  → worker.cancel(article_id)
  → 응답: {"status": "cancelled"}

POST   /api/backup/pause
  → worker.pause()
  → 응답: {"status": "paused"}

POST   /api/backup/resume
  → worker.resume()
  → 응답: {"status": "resumed"}

GET    /api/backup/queue
  → worker.get_status()
  → 응답: {"paused": false, "current": {...}, "pending": [...]}
```

### SSE

```
GET /api/backup/events
  → SSE 스트림
  → Content-Type: text/event-stream
  → 각 이벤트: event: {type}\ndata: {json}\n\n
```

FastAPI에서 `StreamingResponse` + `EventBus.subscribe()`로 구현.

```python
@router.get("/events")
async def backup_events():
    queue = event_bus.subscribe()
    async def generate():
        try:
            while True:
                event = await queue.get()
                yield f"event: {event.type}\ndata: {json.dumps(event.data)}\n\n"
        finally:
            event_bus.unsubscribe(queue)
    return StreamingResponse(generate(), media_type="text/event-stream")
```

## FastAPI 통합 (main.py)

```python
@app.on_event("startup")
async def startup():
    engine = create_engine_and_tables()
    client = ArcaClient()
    event_bus = EventBus()
    service = BackupService(engine=engine, client=client)
    worker = BackupWorker(service=service, event_bus=event_bus)
    asyncio.create_task(worker.run())
```

## DB 변경

`Article.backup_status`에 `"cancelled"` 값 추가. 기존 str 필드이므로 스키마 변경 없음.

## 에러 처리

- 게시글 가져오기 실패 (네트워크/CF 차단): `Article.backup_status = "failed"`, `backup_error`에 사유 기록, 다음 게시글로 진행.
- 서버 재시작 시: `in_progress` 상태인 Article을 `pending`으로 되돌리고 워커가 다시 처리. (startup 시 복구 로직)

## 범위 외

- 큐 순서 변경 (우선순위)
- 재시도 자동화 (수동 재요청으로 대체)
- 외부 링크(렐름/프로톤) 다운로드
