# Open Backup Folder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "백업 폴더 열기" button in the backup detail page header that opens the article's backup folder in the OS file explorer (Explorer / Finder / xdg-open).

**Architecture:** New FastAPI POST endpoint `/api/backup/open-folder/{article_id}` launches a detached subprocess (`explorer` / `open` / `xdg-open`) targeting `data/articles/{id}/downloads/` if present, else `data/articles/{id}/`. Path is resolved and validated to stay under `data_dir`. Frontend adds a button + API client method that calls it and shows a toast only on error.

**Tech Stack:** FastAPI, Python `subprocess`, React + TypeScript, shadcn/ui Button, sonner toast.

**Spec:** `docs/superpowers/specs/2026-04-20-open-backup-folder-design.md`

---

## File Structure

- **Create:** none
- **Modify:**
  - `app/api/backup.py` — add `open-folder/{article_id}` endpoint inside `create_backup_router`
  - `web/src/api/client.ts` — add `backupApi.openFolder(id)`
  - `web/src/pages/BackupDetailPage.tsx` — add button in the header action row

No new files. Each modified file has a single additive change.

---

## Task 1: Backend endpoint — `open-folder/{article_id}`

**Files:**
- Modify: `app/api/backup.py` (add new route inside `create_backup_router`, before the final `return router`)

- [ ] **Step 1: Add `sys` import and `subprocess` import at top of file**

Open `app/api/backup.py`. The top of the file currently has:

```python
from __future__ import annotations

import asyncio
import json

from pathlib import Path

from fastapi import APIRouter, Body, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse
```

Change it to:

```python
from __future__ import annotations

import asyncio
import json
import subprocess
import sys

from pathlib import Path

from fastapi import APIRouter, Body, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse
```

- [ ] **Step 2: Add the `open-folder` route**

Inside `create_backup_router(worker, event_bus, engine=None)`, insert the following route **just before** the final `return router` line (currently at the bottom of the function):

```python
    @router.post("/open-folder/{article_id}")
    async def open_backup_folder(article_id: int):
        """article의 백업 폴더를 OS 파일 탐색기로 연다.

        - data/articles/{id}/downloads/ 가 있으면 그 폴더를
        - 없으면 data/articles/{id}/ 를 연다
        - 둘 다 없으면 에러
        """
        data_dir = Path(worker._service._data_dir) if worker else Path("data")
        data_root = data_dir.resolve()

        article_dir = (data_dir / "articles" / str(article_id)).resolve()
        downloads_dir = article_dir / "downloads"

        # path traversal 방지: article_dir 가 data_root 하위인지 검증
        try:
            article_dir.relative_to(data_root)
        except ValueError:
            return {"error": "invalid path"}

        target = downloads_dir if downloads_dir.exists() else article_dir
        if not target.exists():
            return {"error": "folder not found"}

        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", str(target)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except FileNotFoundError:
            return {"error": "file explorer not available"}
        except Exception as e:
            return {"error": f"failed to open: {e}"}

        return {"status": "opened", "path": str(target)}
```

- [ ] **Step 3: Manual smoke test — endpoint exists and responds for a real article**

Start the dev server in another terminal (user-run): `run.bat` or equivalent. Then from a new terminal:

```bash
# replace 123 with any article_id that exists in the current dev DB
curl -X POST http://localhost:8000/api/backup/open-folder/123
```

Expected response (if folder exists):
```json
{"status":"opened","path":"C:\\...\\data\\articles\\123\\downloads"}
```

Or `{"status":"opened","path":"...\\data\\articles\\123"}` if `downloads/` doesn't exist yet.

And a File Explorer (on Windows) window should pop open showing that folder.

If no such article exists yet, pick any `article_id` you can see on the History page in the UI, or create one by running a backup.

Expected response for a non-existent article id (e.g. `999999`):
```json
{"error":"folder not found"}
```

- [ ] **Step 4: Commit**

```bash
git add app/api/backup.py
git commit -m "feat(backup): add open-folder endpoint to launch OS file explorer"
```

---

## Task 2: Frontend API client — `backupApi.openFolder`

**Files:**
- Modify: `web/src/api/client.ts` (add method inside `backupApi` object)

- [ ] **Step 1: Add `openFolder` method to `backupApi`**

In `web/src/api/client.ts`, find the `backupApi` object (starts around line 148, `export const backupApi = {`). Add this method inside it — a good place is right after `markDownloadComplete`:

```ts
  openFolder: (articleId: number) =>
    post<{ status?: string; path?: string; error?: string }>(`/backup/open-folder/${articleId}`),
```

For reference, the surrounding existing code looks like:

```ts
  markDownloadComplete: (articleId: number) =>
    post<{ status: string }>(`/backup/complete-download/${articleId}`),

  getCandidates: (articleId: number) =>
    ...
```

Insert between `markDownloadComplete` and `getCandidates`, keeping the trailing comma pattern.

- [ ] **Step 2: Typecheck**

From the repo root:

```bash
cd web && npx tsc --noEmit
```

Expected: no errors. (If the project uses a different typecheck script like `npm run typecheck`, that's fine too — pick whatever passes for the rest of the file.)

- [ ] **Step 3: Commit**

```bash
git add web/src/api/client.ts
git commit -m "feat(backup): add openFolder method to backup API client"
```

---

## Task 3: Frontend button in BackupDetailPage header

**Files:**
- Modify: `web/src/pages/BackupDetailPage.tsx` (header action row, around lines 109–133)

- [ ] **Step 1: Add the button next to "원본 보기 (Sentinel)"**

In `web/src/pages/BackupDetailPage.tsx`, locate the action button row. It currently contains (around L109–154):

```tsx
      {/* 액션 */}
      <div className="flex items-center gap-2">
        {article.download_complete ? (
          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium border bg-emerald-100 text-emerald-700 border-emerald-300">
            다운로드 완료
          </span>
        ) : (
          <Button size="sm" variant="outline" onClick={async () => {
            await backupApi.markDownloadComplete(article.id)
            backupApi.getDetail(article.id).then(d => {
              setDetail(d)
            })
          }}>
            다운로드 완료 처리
          </Button>
        )}
        <Button size="sm" variant="outline" onClick={handleRetry}>재시도</Button>
        <Link to={`/article/${article.channel_slug}/${article.id}`}>
          <Button size="sm" variant="outline">원본 보기 (Sentinel)</Button>
        </Link>
        {article.url && (
          <a href={article.url} target="_blank" rel="noopener noreferrer">
            <Button size="sm" variant="ghost">arca.live에서 열기 ↗</Button>
          </a>
        )}
```

Insert the new button **immediately after** the "원본 보기 (Sentinel)" `<Link>` block and **before** the `{article.url && (...)}` block, so the final section reads:

```tsx
        <Button size="sm" variant="outline" onClick={handleRetry}>재시도</Button>
        <Link to={`/article/${article.channel_slug}/${article.id}`}>
          <Button size="sm" variant="outline">원본 보기 (Sentinel)</Button>
        </Link>
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
        {article.url && (
          <a href={article.url} target="_blank" rel="noopener noreferrer">
            <Button size="sm" variant="ghost">arca.live에서 열기 ↗</Button>
          </a>
        )}
```

No new imports needed — `Button`, `backupApi`, and `toast` are already imported at the top of the file.

- [ ] **Step 2: Typecheck**

```bash
cd web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Manual test — happy path**

Start the dev servers (backend + web) as usual (`run.bat` or per project convention). In the browser:

1. Open any backup detail page at `/backup/<article_id>` for an article that has completed backing up.
2. Verify the header shows a new "백업 폴더 열기" button between "원본 보기 (Sentinel)" and "arca.live에서 열기 ↗".
3. Click it.
4. Expected: File Explorer opens showing `data/articles/<id>/downloads/` (if that folder exists) or `data/articles/<id>/` (if it doesn't). No toast appears.

- [ ] **Step 4: Manual test — error path**

To verify error handling without a hard-to-reproduce scenario, temporarily rename the article folder:

1. With the dev server still running, rename `data/articles/<id>` to `data/articles/<id>_bak` for some id you have open in the browser.
2. Click "백업 폴더 열기" on that article's detail page.
3. Expected: No Explorer opens; a red toast "폴더를 열 수 없습니다" appears.
4. Rename the folder back to restore state.

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/BackupDetailPage.tsx
git commit -m "feat(backup): add 'open backup folder' button to detail page header"
```

---

## Self-Review

**Spec coverage:**

- ✅ `downloads/` 우선, 없으면 article 폴더 폴백 → Task 1 Step 2 (`target = downloads_dir if downloads_dir.exists() else article_dir`)
- ✅ 둘 다 없으면 에러 → Task 1 Step 2 (`if not target.exists(): return {"error": "folder not found"}`)
- ✅ 성공 시 toast 없음, 실패 시 toast → Task 3 Step 1
- ✅ 플랫폼 분기 (Windows/macOS/Linux) → Task 1 Step 2
- ✅ path traversal 방어 → Task 1 Step 2 (`article_dir.relative_to(data_root)`)
- ✅ 비동기 실행 (block 안 함) → Task 1 Step 2 (`subprocess.Popen`)
- ✅ 버튼 배치 "원본 보기 (Sentinel)" 근처 → Task 3 Step 1
- ✅ API 클라이언트 메서드 추가 → Task 2 Step 1

**Placeholder scan:** No TBD/TODO. All code blocks are concrete. Error messages are specific strings.

**Type consistency:**
- Backend returns `{status, path}` or `{error}` — matches frontend type `{ status?: string; path?: string; error?: string }`.
- `openFolder(articleId: number)` signature matches backend `article_id: int` path param.
- Button uses existing imports only (`Button`, `backupApi`, `toast`) — no new imports needed, verified against file head.

Plan is complete.
