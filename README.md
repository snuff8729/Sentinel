# Sentinel

arca.live 게시글 백업 및 자료 관리 도구.

게시글을 오프라인에서 열람할 수 있도록 HTML + 미디어를 백업하고, 다운로드 링크를 자동 분류하며, 버전 관리와 업데이트 감지를 제공합니다.

## 주요 기능

### 게시글 브라우징
- 채널 목록 조회 (카테고리, 개념글, 검색, 페이지네이션)
- 게시글 상세 조회 (본문 + 댓글)
- Cloudflare 우회 (curl-cffi 브라우저 impersonation)

### 백업
- 게시글 HTML 백업 (본문 + 댓글, 오프라인 열람 가능)
- 첨부 미디어 다운로드 (이미지, GIF, 비디오, 음성)
- 아카콘 공용 저장소 (중복 다운로드 방지)
- 도메인별 다운로드 딜레이/동시실행 설정

### 다운로드 큐
- 백그라운드 순차 처리
- 일시정지 / 재개 / 취소
- SSE 실시간 진행도
- 도메인별 속도 제어 (arca.live, namu.la 등)

### 링크 분석
- 도메인 기반 자동 분류 (Proton Drive, Realm, Chub 등)
- 같은 작성자 원본 게시글 자동 탐색 (depth 1)
- Realm 캐릭터 자동 다운로드

### 버전 관리
- 게시글을 버전 그룹으로 묶기 (수동 + 자동)
- 임베딩 기반 유사 게시글 감지 (sqlite-vec)
- 유사도 >= 80%일 때 자동 그룹 연결
- 게시글 목록에서 업데이트 감지 토글

### 사용자 관리
- 팔로우 (게시글 목록에서 강조 표시)
- 최근 접속 채널 기록

### 웹 UI
- React + TypeScript + shadcn/ui
- 채널 / 게시글 상세 / 다운로드 큐 / 백업 이력 / 버전 관리 / 설정

## 개발 환경 구성

### 원클릭 설치 (Windows)

외부 설치 없이 Python, Node.js, 의존성을 모두 자동으로 설치합니다.

```powershell
git clone <repo>
cd sentinel
.\install.ps1    # 설치 (최초 1회)
.\run.ps1        # 서버 실행
.\update.ps1     # 업데이트 (git pull + 재빌드)
```

> `runtime/` 폴더에 내장 Python, Node.js, uv가 설치됩니다.

### 수동 설치

#### 요구 사항
- Python 3.14+
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) (Python 패키지 매니저)

#### 백엔드 설치

```bash
git clone <repo>
cd sentinel
uv sync
```

#### 프론트엔드 설치

```bash
cd web
npm install
```

### 환경 변수

```bash
cp .env.example .env
```

`.env` 파일에 arca.live 쿠키를 설정합니다:

```
ARCA_COOKIES="arca.nick=...; arca.at=...; ..."
```

쿠키는 arca.live에 로그인한 브라우저의 개발자 도구 → Network 탭에서 복사할 수 있습니다.

## 실행

### 프론트엔드 빌드

```bash
cd web
npm run build
```

### 서버 실행

```bash
uv run uvicorn app.main:app --reload
```

`http://localhost:8000`에서 접속합니다.

### 개발 모드 (핫 리로드)

터미널 1 — 백엔드:
```bash
uv run uvicorn app.main:app --reload
```

터미널 2 — 프론트엔드:
```bash
cd web
npm run dev
```

`http://localhost:5173`에서 접속합니다 (API는 8000으로 프록시됩니다).

### 테스트

```bash
uv run pytest tests/ -v
```
