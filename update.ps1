# Sentinel - 업데이트 스크립트
# git pull 후 의존성 업데이트 + 프론트엔드 재빌드

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
$RUNTIME = Join-Path $ROOT "runtime"
$UV_DIR = Join-Path $RUNTIME "uv"
$NODE_DIR = Join-Path $RUNTIME "node"
$UV = Join-Path $UV_DIR "uv.exe"
$NPM = Join-Path $NODE_DIR "npm.cmd"

if (!(Test-Path $UV)) {
    Write-Host "Sentinel이 설치되지 않았습니다. install.ps1을 먼저 실행해주세요." -ForegroundColor Red
    exit 1
}

$env:UV_PYTHON_INSTALL_DIR = Join-Path $RUNTIME "python"
$env:PATH = "$NODE_DIR;$env:PATH"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Sentinel 업데이트" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. git pull
Write-Host "[1/3] 소스코드 업데이트..." -ForegroundColor Yellow
Push-Location $ROOT
git pull origin main
Pop-Location
Write-Host "  완료" -ForegroundColor Green

# 2. Python 의존성
Write-Host "[2/3] Python 의존성 업데이트..." -ForegroundColor Yellow
Push-Location $ROOT
& $UV sync --quiet
Pop-Location
Write-Host "  완료" -ForegroundColor Green

# 3. 프론트엔드 재빌드
Write-Host "[3/3] 프론트엔드 재빌드..." -ForegroundColor Yellow
Push-Location (Join-Path $ROOT "web")
& $NPM install --silent 2>$null
& $NPM run build 2>$null
Pop-Location
Write-Host "  완료" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  업데이트 완료!" -ForegroundColor Cyan
Write-Host "  run.ps1 을 실행하여 서버를 시작하세요." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
