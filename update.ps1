# Sentinel - Update Script

[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$ErrorActionPreference = "Stop"

$ROOT = $PSScriptRoot
$RUNTIME = Join-Path $ROOT "runtime"
$UV_DIR = Join-Path $RUNTIME "uv"
$NODE_DIR = Join-Path $RUNTIME "node"
$UV = Join-Path $UV_DIR "uv.exe"
$NPM = Join-Path $NODE_DIR "npm.cmd"

if (!(Test-Path $UV)) {
    Write-Host "Sentinel is not installed. Please run install.bat first." -ForegroundColor Red
    exit 1
}

$env:UV_PYTHON_INSTALL_DIR = Join-Path $RUNTIME "python"
$env:PATH = "$NODE_DIR;$env:PATH"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Sentinel - Update" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Pulling latest code..." -ForegroundColor Yellow
Push-Location $ROOT
git pull origin main
Pop-Location
Write-Host "  Done" -ForegroundColor Green

Write-Host "[2/3] Updating Python dependencies..." -ForegroundColor Yellow
Push-Location $ROOT
& $UV sync --quiet
Pop-Location
Write-Host "  Done" -ForegroundColor Green

Write-Host "[3/3] Rebuilding frontend..." -ForegroundColor Yellow
Push-Location (Join-Path $ROOT "web")
$ErrorActionPreference = "Continue"
& $NPM install --silent 2>&1 | Out-Null
& $NPM run build 2>&1 | Out-Null
$ErrorActionPreference = "Stop"
Pop-Location
Write-Host "  Done" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Update complete!" -ForegroundColor Cyan
Write-Host "  Run run.bat to start the server." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
