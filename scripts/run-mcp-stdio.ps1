Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "Expected virtualenv python at $python"
}

Push-Location $repoRoot
try {
  & $python -m finkernel.transport.mcp.stdio_runner
} finally {
  Pop-Location
}
