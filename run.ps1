# Sentinel - Run Script

[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$ErrorActionPreference = "Stop"

$ROOT = $PSScriptRoot
$RUNTIME = Join-Path $ROOT "runtime"
$UV_DIR = Join-Path $RUNTIME "uv"
$NODE_DIR = Join-Path $RUNTIME "node"
$UV = Join-Path $UV_DIR "uv.exe"

if (!(Test-Path $UV)) {
    Write-Host "Sentinel is not installed. Please run install.bat first." -ForegroundColor Red
    exit 1
}

$env:UV_PYTHON_INSTALL_DIR = Join-Path $RUNTIME "python"
$env:PATH = "$NODE_DIR;$env:PATH"

$PORT = if ($args[0]) { $args[0] } else { "8000" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Sentinel Server" -ForegroundColor Cyan
Write-Host "  http://localhost:$PORT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Push-Location $ROOT
& $UV run uvicorn app.main:app --host 0.0.0.0 --port $PORT
Pop-Location
