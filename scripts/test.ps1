$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CacheRoot = "D:\ProjectCaches"

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PIP_CACHE_DIR = Join-Path $CacheRoot "pip"
$env:PYTHONPYCACHEPREFIX = Join-Path $CacheRoot "python"
$env:TEMP = Join-Path $CacheRoot "temp"
$env:TMP = $env:TEMP

Push-Location $ProjectRoot
try {
    python -m unittest discover -s tests -v
}
finally {
    Pop-Location
}

