# Sentinel - Install Script
# Embedded Python (via uv) + Embedded Node.js

[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$ErrorActionPreference = "Stop"

$ROOT = $PSScriptRoot
$RUNTIME = Join-Path $ROOT "runtime"
$UV_DIR = Join-Path $RUNTIME "uv"
$NODE_DIR = Join-Path $RUNTIME "node"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Sentinel - Install" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Install uv ---
if (!(Test-Path (Join-Path $UV_DIR "uv.exe"))) {
    Write-Host "[1/5] Downloading uv..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $UV_DIR | Out-Null

    $UV_VERSION = "0.7.12"
    $UV_URL = "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-pc-windows-msvc.zip"
    $UV_ZIP = Join-Path $RUNTIME "uv.zip"

    Invoke-WebRequest -Uri $UV_URL -OutFile $UV_ZIP
    Expand-Archive -Path $UV_ZIP -DestinationPath $UV_DIR -Force
    $inner = Get-ChildItem $UV_DIR -Directory | Select-Object -First 1
    if ($inner -and (Test-Path (Join-Path $inner.FullName "uv.exe"))) {
        Move-Item (Join-Path $inner.FullName "*") $UV_DIR -Force
        Remove-Item $inner.FullName -Recurse -Force
    }
    Remove-Item $UV_ZIP -Force
    Write-Host "  uv installed" -ForegroundColor Green
} else {
    Write-Host "[1/5] uv already installed" -ForegroundColor Green
}

$UV = Join-Path $UV_DIR "uv.exe"

# --- 2. Install Python (managed by uv) ---
Write-Host "[2/5] Installing Python..." -ForegroundColor Yellow
$env:UV_PYTHON_INSTALL_DIR = Join-Path $RUNTIME "python"
& $UV python install 3.14 --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    & $UV python install 3.13 --quiet
}
Write-Host "  Python installed" -ForegroundColor Green

# --- 3. Install Node.js ---
if (!(Test-Path (Join-Path $NODE_DIR "node.exe"))) {
    Write-Host "[3/5] Downloading Node.js..." -ForegroundColor Yellow
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
    Write-Host "  Node.js installed" -ForegroundColor Green
} else {
    Write-Host "[3/5] Node.js already installed" -ForegroundColor Green
}

$NPM = Join-Path $NODE_DIR "npm.cmd"

# --- 4. Install Python dependencies ---
Write-Host "[4/5] Installing Python dependencies..." -ForegroundColor Yellow
Push-Location $ROOT
& $UV sync --quiet
Pop-Location
Write-Host "  Dependencies installed" -ForegroundColor Green

# --- 5. Build frontend ---
Write-Host "[5/5] Building frontend..." -ForegroundColor Yellow
$env:PATH = "$NODE_DIR;$env:PATH"
Push-Location (Join-Path $ROOT "web")
& $NPM install --silent 2>$null
& $NPM run build 2>$null
Pop-Location
Write-Host "  Frontend built" -ForegroundColor Green

# --- Create .env ---
$ENV_FILE = Join-Path $ROOT ".env"
if (!(Test-Path $ENV_FILE)) {
    Copy-Item (Join-Path $ROOT ".env.example") $ENV_FILE
    Write-Host ""
    Write-Host "  .env file created." -ForegroundColor Yellow
    Write-Host "  Please set your arca.live cookies in .env" -ForegroundColor Yellow
}

# --- Create data directory ---
$DATA_DIR = Join-Path $ROOT "data"
if (!(Test-Path $DATA_DIR)) {
    New-Item -ItemType Directory -Force -Path $DATA_DIR | Out-Null
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Install complete!" -ForegroundColor Cyan
Write-Host "  Run run.bat to start the server." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
