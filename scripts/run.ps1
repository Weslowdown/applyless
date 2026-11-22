$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CacheRoot = "D:\ProjectCaches"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$env:PIP_CACHE_DIR = Join-Path $CacheRoot "pip"
$env:PYTHONPYCACHEPREFIX = Join-Path $CacheRoot "python"
$env:NPM_CONFIG_CACHE = Join-Path $CacheRoot "npm"
$env:PNPM_STORE_DIR = Join-Path $CacheRoot "pnpm"
$env:UV_CACHE_DIR = Join-Path $CacheRoot "uv"
$env:TEMP = Join-Path $CacheRoot "temp"
$env:TMP = $env:TEMP

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Creating the local Python environment on D drive..."
    python -m venv --system-site-packages (Join-Path $ProjectRoot ".venv")
    & $Python -m pip install -e $ProjectRoot --no-build-isolation
}

Push-Location $ProjectRoot
try {
    & $Python -m applyless serve --open
}
finally {
    Pop-Location
}

