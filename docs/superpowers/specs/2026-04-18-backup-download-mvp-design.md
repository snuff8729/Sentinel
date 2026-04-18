# MVP: 게시글 백업 + 다운로드 시스템

## 목적

사용자가 선택한 arca.live 게시글의 상세 페이지를 완전히 오프라인에서 볼 수 있도록 백업하고, 첨부된 모든 미디어(이미지, gif, 비디오, 음성)와 아카콘을 로컬에 다운로드한다.

## 파일 구조

### 저장 디렉토리

```
data/
  emoticons/                    # 아카콘 공용 저장소 (여러 게시글에서 공유)
    227952228.png
    338401012.gif
  articles/
    168039133/
      backup.html               # 로컬 경로로 치환된 오프라인용 HTML
      images/
        fad59953...webp
        6327a8eb...png
      videos/
        abc123...mp4
      audio/
        def456...mp3
    168046805/
      backup.html
      images/
        ...
```

- 게시글 ID 기반 플랫 구조. 채널/게시자 정보는 DB에서 관리.
- 아카콘(`arca-emoticon` 클래스)은 `data/emoticons/`에 한 번만 저장. `data-id` 속성을 파일명으로 사용.
- 게시글 내 미디어는 타입별 하위 폴더(`images/`, `videos/`, `audio/`)에 저장.
- HTML 백업 시 모든 리소스 URL을 로컬 상대 경로로 치환하여 오프라인에서 브라우저로 바로 열 수 있도록 함.
  - 게시글 미디어: `./images/filename.png`
  - 아카콘: `../../emoticons/227952228.png` (상대 경로)

### 코드 구조

```
app/
  db/
    __init__.py
    engine.py          # SQLModel 엔진/세션 설정
    models.py          # Article, Download SQLModel 테이블
    repository.py      # CRUD 함수
  backup/
    __init__.py
    service.py         # 백업 오케스트레이션 (HTML 가져오기 → 미디어 수집 → 다운로드 → 치환 → 저장)
    media.py           # HTML에서 미디어 URL 추출, URL→로컬 경로 치환
    queue.py           # 다운로드 큐 (도메인별 동시 실행/딜레이 관리)
  scraper/
    arca/              # 기존 스크래퍼 (변경 없음)
```

## DB 스키마 (SQLModel)

### Article

게시글 메타 정보 + 백업 상태 추적.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | int, PK | arca.live 게시글 ID |
| channel_slug | str | 채널 slug (예: "characterai") |
| title | str | 게시글 제목 |
| author | str | 작성자 |
| category | str, nullable | 카테고리 |
| created_at | datetime | 게시글 작성 시각 |
| url | str | 원본 URL |
| backup_status | str | "pending" / "in_progress" / "completed" / "failed" |
| backup_error | str, nullable | 실패 사유 |
| backed_up_at | datetime, nullable | 백업 완료 시각 |

### Download

개별 파일 다운로드 추적. 하나의 Article에 여러 Download가 연결됨.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | int, PK, auto | 자동 증가 ID |
| article_id | int, FK → Article | 소속 게시글 |
| url | str | 원본 다운로드 URL |
| local_path | str | 로컬 저장 경로 (data/ 기준 상대경로) |
| file_type | str | "image" / "video" / "audio" / "emoticon" |
| status | str | "pending" / "in_progress" / "completed" / "failed" |
| error | str, nullable | 실패 사유 |

## 다운로드 큐

### 도메인별 동시 실행 + 딜레이

도메인별로 동시 실행 개수와 요청 간 최소 딜레이를 설정. 같은 도메인에 대해 동시 실행 한도와 딜레이가 모두 적용됨.

| 도메인 | 동시 실행 | 딜레이 |
|--------|----------|--------|
| arca.live | 1 | 3초 |
| namu.la | 3 | 1초 |
| 기타(default) | 2 | 1초 |

### 설정

`.env`에서 오버라이드 가능:

```
DOWNLOAD_ARCA_LIVE_CONCURRENCY=1
DOWNLOAD_ARCA_LIVE_DELAY=3
DOWNLOAD_NAMU_LA_CONCURRENCY=3
DOWNLOAD_NAMU_LA_DELAY=1
DOWNLOAD_DEFAULT_CONCURRENCY=2
DOWNLOAD_DEFAULT_DELAY=1
```

### 동작 방식

- `queue.py`는 도메인별 세마포어 + 마지막 요청 시각을 관리.
- 다운로드 요청이 들어오면 URL에서 도메인을 추출하고, 해당 도메인의 세마포어를 획득한 뒤, 마지막 요청 이후 딜레이만큼 대기 후 실행.
- asyncio 기반. `ArcaClient`의 curl-cffi는 동기이므로 `asyncio.to_thread`로 감싸서 사용.

## 백업 처리 흐름

하나의 게시글 백업 과정:

1. `Article` 레코드 생성 (또는 기존 것 조회), `backup_status = "in_progress"`로 업데이트
2. 스크래퍼(`ArcaChannel.get_article`)로 상세 페이지 HTML 가져오기
3. HTML에서 미디어 URL 수집:
   - `img` 태그 → file_type 판별 (확장자 기반: png/jpg/webp→image, gif→image, mp4→video, mp3/ogg→audio)
   - `img.arca-emoticon` → file_type="emoticon", `data-id`로 식별
   - `video` 태그 → file_type="video"
   - `audio` 태그 → file_type="audio"
4. 각 미디어에 대해 `Download` 레코드 생성 (`status="pending"`)
5. 다운로드 큐에 등록 → 도메인별 동시 실행/딜레이 적용하여 파일 다운로드
   - 아카콘: `data/emoticons/{data_id}.{ext}` — 이미 존재하면 스킵
   - 그 외: `data/articles/{article_id}/{type}/{filename}`
6. 각 다운로드 완료/실패 시 `Download.status` 업데이트
7. 모든 다운로드 완료 후:
   - HTML 내 모든 미디어 URL을 로컬 상대 경로로 치환
   - `data/articles/{article_id}/backup.html`로 저장
8. 최종 상태 결정:
   - 모든 Download가 completed → `Article.backup_status = "completed"`
   - 하나라도 failed → `Article.backup_status = "failed"`, `backup_error`에 실패 요약 기록
   - 부분 백업(일부만 성공)은 유지 — HTML과 성공한 파일은 보존

## 완료 스킵

- 백업 요청 시 `Article.backup_status == "completed"`이면 스킵.
- 강제 재다운로드 옵션: `force=True` 파라미터로 완료 상태여도 재실행 가능.

## 에러 처리

- 미디어 하나가 실패해도 나머지는 계속 진행 (부분 백업 보존).
- HTTP 에러, 타임아웃, 파일 쓰기 에러 등을 `Download.error`에 기록.
- `Article.backup_error`에는 실패한 파일 개수/목록 요약 저장.

## 범위 외 (다음 단계)

- 프로톤/렐름 외부 링크 다운로드
- 버전 관리 (같은 자료 버전별 묶기)
- 연결 관계 (파생 자료 양방향 연결)
- 웹 UI
- 조회/필터
