# 백업 폴더 열기 (Open Backup Folder)

날짜: 2026-04-20

## 개요

백업 상세 페이지(`BackupDetailPage`) 헤더에서 해당 게시글의 백업 자료가 저장된 폴더를 OS 기본 파일 탐색기(Windows Explorer / macOS Finder / Linux 파일 관리자)로 여는 기능.

Sentinel은 로컬에서 실행되는 데스크톱-유사 도구이므로 FastAPI 서버의 subprocess가 곧 사용자 데스크톱의 탐색기를 띄운다.

## 동작 요구사항

사용자가 헤더의 "백업 폴더 열기" 버튼을 누르면:

1. `data/articles/{id}/downloads/` 가 존재하면 그 폴더를 연다.
2. 없으면 `data/articles/{id}/` 를 연다 (`backup.html`, `images/`, `videos/`, `audio/` 등이 있음).
3. 둘 다 없으면 (예: 이미 삭제된 게시글) 실패 toast 표시.

성공 시 별도 toast는 띄우지 않는다 (탐색기 창이 뜨는 것 자체가 피드백).

## 백엔드 설계

### 새 엔드포인트

`POST /api/backup/open-folder/{article_id}` → `{"status": "opened", "path": "..."} | {"error": "..."}`

위치: `app/api/backup.py` 의 `create_backup_router` 안에 다른 엔드포인트와 같은 스타일로 추가.

### 경로 결정

```python
data_dir = Path(worker._service._data_dir) if worker else Path("data")
article_dir = (data_dir / "articles" / str(article_id)).resolve()
downloads_dir = article_dir / "downloads"
target = downloads_dir if downloads_dir.exists() else article_dir
```

### 안전장치 (path traversal 방지)

`data_dir.resolve()` 기준으로 `target` 이 그 하위에 있는지 검증. `article_id` 는 int 파라미터라 실제 traversal 위험은 낮지만 방어적으로 둔다.

```python
data_root = data_dir.resolve()
if not str(target).startswith(str(data_root)):
    return {"error": "invalid path"}
if not target.exists():
    return {"error": "folder not found"}
```

### 플랫폼 감지 및 실행

`sys.platform` 기반 분기:

| 플랫폼 | 명령 |
|--------|------|
| `win32` | `subprocess.Popen(["explorer", str(target)])` |
| `darwin` | `subprocess.Popen(["open", str(target)])` |
| 그 외 (Linux) | `subprocess.Popen(["xdg-open", str(target)])` |

비동기로 띄우고 (`Popen` 은 block 안 함) 바로 응답 반환. `subprocess.run(check=True)` 아님에 주의 — `explorer` 는 성공해도 exit code 1을 반환하는 경우가 있어 예외 처리가 복잡해짐.

예외 발생 시 (`FileNotFoundError` 등) `{"error": "..."}` 반환.

## 프론트엔드 설계

### 1. API 클라이언트

`web/src/api/client.ts` 의 `backupApi` 에 메서드 추가:

```ts
openFolder: (id: number) =>
  request<{ status?: string; path?: string; error?: string }>(`/backup/open-folder/${id}`, { method: 'POST' }),
```

### 2. 버튼 배치

`web/src/pages/BackupDetailPage.tsx` 의 액션 버튼 영역 (L109~ 의 `<div className="flex items-center gap-2">` 내부, "원본 보기 (Sentinel)" 근처) 에 추가:

```tsx
<Button size="sm" variant="outline" onClick={async () => {
  try {
    const res = await backupApi.openFolder(article.id)
    if (res.error) toast.error('폴더를 열 수 없습니다')
  } catch {
    toast.error('폴더를 열 수 없습니다')
  }
}}>
  백업 폴더 열기
</Button>
```

버튼은 게시글 삭제 여부와 관계없이 항상 표시. 실제로 폴더가 없을 때만 서버가 에러를 반환하고 toast로 알림.

## 보안/범위

- 이 엔드포인트는 *서버가 돌아가는 기기* 의 탐색기를 연다. Sentinel은 로컬 사용 전제이므로 의도된 동작이다.
- 외부 네트워크/LAN 노출을 한다면 이 엔드포인트는 원치 않는 동작을 할 수 있으나, Sentinel 의 기본 실행 방식(`run.bat`, `run.ps1` 로 로컬 uvicorn)에서는 문제 없음.
- 인자는 `article_id` (int) 뿐이므로 임의 경로 주입 불가. 추가로 `data_dir` 하위 검증도 둔다.

## 비범위 (YAGNI)

- 파일별 "위치 열기" (`explorer /select,<file>`) 는 이번 범위 밖. 필요해지면 별도로.
- 다운로드 완료 후 자동으로 폴더 열기 같은 트리거는 안 함.
- 로그인/권한 시스템 없음 (로컬 툴).

## 테스트 계획

- 수동: Windows 에서 탐색기가 올바른 폴더로 열리는지 확인.
- 수동: 다운로드가 없는 게시글에서 article 폴더로 폴백되는지 확인.
- 수동: 존재하지 않는 `article_id` 로 호출 시 에러 toast.
- 자동 테스트는 subprocess 가 플랫폼 의존이라 추가하지 않음 (프로젝트에 기존 API 테스트 관행이 없어 보임 — 필요 시 mock 기반으로 추가 가능).
