param(
    [string]$DataDir = ".finkernel",
    [string]$ProfileStorePath = "config/persona-profiles.json",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating local Python virtual environment..."
    python -m venv .venv
}

if (-not $SkipInstall) {
    Write-Host "Installing FinKernel into the local virtual environment..."
    & $venvPython -m pip install -e .
}

$configDir = Split-Path $ProfileStorePath -Parent
if ($configDir -and -not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir | Out-Null
}

if (-not (Test-Path $ProfileStorePath)) {
    '{"profiles":[]}' | Set-Content -Path $ProfileStorePath -Encoding UTF8
}

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
}

$envPath = Join-Path $repoRoot ".env"
$liteEnv = [ordered]@{
    STORAGE_BACKEND = "file"
    PROFILE_DATA_DIR = $DataDir
    PROFILE_STORE_PATH = $ProfileStorePath
    APP_PORT = "8000"
}
if (-not (Test-Path $envPath)) {
    @"
STORAGE_BACKEND=$($liteEnv.STORAGE_BACKEND)
PROFILE_DATA_DIR=$($liteEnv.PROFILE_DATA_DIR)
PROFILE_STORE_PATH=$($liteEnv.PROFILE_STORE_PATH)
APP_PORT=$($liteEnv.APP_PORT)
"@ | Set-Content -Path $envPath -Encoding UTF8
}

$stdioConfigPath = Join-Path $repoRoot "config\host-agent-mcp-stdio.local.json"
$stdioConfig = [ordered]@{
    mcpServers = [ordered]@{
        finkernel = [ordered]@{
            command = $venvPython
            args = @("-m", "finkernel.transport.mcp.stdio_runner")
            env = [ordered]@{
                STORAGE_BACKEND = "file"
                PROFILE_DATA_DIR = $DataDir
                PROFILE_STORE_PATH = $ProfileStorePath
            }
        }
    }
}
$stdioConfig | ConvertTo-Json -Depth 8 | Set-Content -Path $stdioConfigPath -Encoding UTF8

Write-Host "Verifying FinKernel Lite runtime..."
$env:STORAGE_BACKEND = $liteEnv.STORAGE_BACKEND
$env:PROFILE_DATA_DIR = $liteEnv.PROFILE_DATA_DIR
$env:PROFILE_STORE_PATH = $liteEnv.PROFILE_STORE_PATH
& $venvPython -m finkernel.transport.mcp.stdio_runner --check

Write-Host ""
Write-Host "FinKernel Lite is ready."
Write-Host "Data directory: $DataDir"
Write-Host "MCP stdio config: $stdioConfigPath"
