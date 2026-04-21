param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot ".venv\\Scripts\\python.exe"

if (-not (Test-Path $python)) {
    throw "Missing virtual environment at $python. Run scripts\\bootstrap-local.ps1 first."
}

Set-Location $repoRoot
& $python -m uvicorn finkernel.main:app --host $Host --port $Port --reload
