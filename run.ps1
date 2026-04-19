# Sentinel - 실행 스크립트

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
$RUNTIME = Join-Path $ROOT "runtime"
$UV_DIR = Join-Path $RUNTIME "uv"
$NODE_DIR = Join-Path $RUNTIME "node"
$UV = Join-Path $UV_DIR "uv.exe"

# 설치 확인
if (!(Test-Path $UV)) {
    Write-Host "Sentinel이 설치되지 않았습니다. install.ps1을 먼저 실행해주세요." -ForegroundColor Red
    exit 1
}

$env:UV_PYTHON_INSTALL_DIR = Join-Path $RUNTIME "python"
$env:PATH = "$NODE_DIR;$env:PATH"

$PORT = if ($args[0]) { $args[0] } else { "8000" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Sentinel 서버 시작" -ForegroundColor Cyan
Write-Host "  http://localhost:$PORT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Push-Location $ROOT
& $UV run uvicorn app.main:app --host 0.0.0.0 --port $PORT
Pop-Location
