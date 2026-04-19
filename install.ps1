# Sentinel - 설치 스크립트
# 내장 Python(uv 관리) + 내장 Node.js로 외부 종속성 없이 설치

[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
$RUNTIME = Join-Path $ROOT "runtime"
$UV_DIR = Join-Path $RUNTIME "uv"
$NODE_DIR = Join-Path $RUNTIME "node"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Sentinel 설치" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. uv 설치 (Python 패키지 매니저) ---
if (!(Test-Path (Join-Path $UV_DIR "uv.exe"))) {
    Write-Host "[1/5] uv 다운로드 중..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $UV_DIR | Out-Null

    $UV_VERSION = "0.7.12"
    $UV_URL = "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-pc-windows-msvc.zip"
    $UV_ZIP = Join-Path $RUNTIME "uv.zip"

    Invoke-WebRequest -Uri $UV_URL -OutFile $UV_ZIP
    Expand-Archive -Path $UV_ZIP -DestinationPath $UV_DIR -Force
    # zip 내부에 폴더가 있을 수 있음
    $inner = Get-ChildItem $UV_DIR -Directory | Select-Object -First 1
    if ($inner -and (Test-Path (Join-Path $inner.FullName "uv.exe"))) {
        Move-Item (Join-Path $inner.FullName "*") $UV_DIR -Force
        Remove-Item $inner.FullName -Recurse -Force
    }
    Remove-Item $UV_ZIP -Force
    Write-Host "  uv 설치 완료" -ForegroundColor Green
} else {
    Write-Host "[1/5] uv 이미 설치됨" -ForegroundColor Green
}

$UV = Join-Path $UV_DIR "uv.exe"

# --- 2. Python 설치 (uv 관리) ---
Write-Host "[2/5] Python 설치 중..." -ForegroundColor Yellow
$env:UV_PYTHON_INSTALL_DIR = Join-Path $RUNTIME "python"
& $UV python install 3.14 --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    & $UV python install 3.13 --quiet
}
Write-Host "  Python 설치 완료" -ForegroundColor Green

# --- 3. Node.js 설치 ---
if (!(Test-Path (Join-Path $NODE_DIR "node.exe"))) {
    Write-Host "[3/5] Node.js 다운로드 중..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $NODE_DIR | Out-Null

    $NODE_VERSION = "v22.16.0"
    $NODE_URL = "https://nodejs.org/dist/$NODE_VERSION/node-$NODE_VERSION-win-x64.zip"
    $NODE_ZIP = Join-Path $RUNTIME "node.zip"

    Invoke-WebRequest -Uri $NODE_URL -OutFile $NODE_ZIP
    Expand-Archive -Path $NODE_ZIP -DestinationPath $RUNTIME -Force
    $extracted = Join-Path $RUNTIME "node-$NODE_VERSION-win-x64"
    if (Test-Path $extracted) {
        Move-Item (Join-Path $extracted "*") $NODE_DIR -Force
        Remove-Item $extracted -Recurse -Force
    }
    Remove-Item $NODE_ZIP -Force
    Write-Host "  Node.js 설치 완료" -ForegroundColor Green
} else {
    Write-Host "[3/5] Node.js 이미 설치됨" -ForegroundColor Green
}

$NODE = Join-Path $NODE_DIR "node.exe"
$NPM = Join-Path $NODE_DIR "npm.cmd"

# --- 4. Python 의존성 설치 ---
Write-Host "[4/5] Python 의존성 설치 중..." -ForegroundColor Yellow
Push-Location $ROOT
& $UV sync --quiet
Pop-Location
Write-Host "  Python 의존성 설치 완료" -ForegroundColor Green

# --- 5. 프론트엔드 빌드 ---
Write-Host "[5/5] 프론트엔드 빌드 중..." -ForegroundColor Yellow
$env:PATH = "$NODE_DIR;$env:PATH"
Push-Location (Join-Path $ROOT "web")
& $NPM install --silent 2>$null
& $NPM run build 2>$null
Pop-Location
Write-Host "  프론트엔드 빌드 완료" -ForegroundColor Green

# --- .env 생성 ---
$ENV_FILE = Join-Path $ROOT ".env"
if (!(Test-Path $ENV_FILE)) {
    Copy-Item (Join-Path $ROOT ".env.example") $ENV_FILE
    Write-Host ""
    Write-Host "  .env 파일이 생성되었습니다." -ForegroundColor Yellow
    Write-Host "  arca.live 쿠키를 .env 파일에 설정해주세요." -ForegroundColor Yellow
}

# --- data 디렉토리 생성 ---
$DATA_DIR = Join-Path $ROOT "data"
if (!(Test-Path $DATA_DIR)) {
    New-Item -ItemType Directory -Force -Path $DATA_DIR | Out-Null
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  설치 완료!" -ForegroundColor Cyan
Write-Host "  run.ps1 을 실행하여 서버를 시작하세요." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
