param(
    [ValidateSet("Ask", "Lite", "Server")]
    [string]$Mode = "Ask",
    [string]$DataDir = ".finkernel",
    [string]$ProfileStorePath = "config/persona-profiles.json",
    [switch]$SkipInstall,
    [switch]$SkipAgentRegistration
)

$ErrorActionPreference = "Stop"

function Prompt-InstallMode {
    Write-Host ""
    Write-Host "Choose a FinKernel installation mode:" -ForegroundColor Cyan
    Write-Host "[1] Lite file storage (recommended): no Docker, local profile files, MCP stdio"
    Write-Host "[2] Server mode: Docker, PostgreSQL, HTTP MCP"

    while ($true) {
        $raw = Read-Host -Prompt "Choose 1-2 [1]"
        if ([string]::IsNullOrWhiteSpace($raw) -or $raw -eq "1") {
            return "Lite"
        }
        if ($raw -eq "2") {
            return "Server"
        }
        Write-Host "Please enter 1 or 2." -ForegroundColor Yellow
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$resolvedMode = if ($Mode -eq "Ask") { Prompt-InstallMode } else { $Mode }

if ($resolvedMode -eq "Lite") {
    Write-Host ""
    Write-Host "Starting FinKernel Lite setup..." -ForegroundColor Green
    & (Join-Path $PSScriptRoot "bootstrap-lite.ps1") `
        -DataDir $DataDir `
        -ProfileStorePath $ProfileStorePath `
        -SkipInstall:$SkipInstall
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Starting FinKernel Server setup..." -ForegroundColor Green
& (Join-Path $PSScriptRoot "bootstrap-local.ps1") `
    -SkipAgentRegistration:$SkipAgentRegistration
exit $LASTEXITCODE
