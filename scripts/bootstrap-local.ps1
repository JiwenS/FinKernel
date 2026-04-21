param(
    [switch]$SkipInstall,
    [switch]$SkipAgentRegistration
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Ensure-Directory {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function New-LocalVenv {
    param(
        [string]$TargetPath
    )

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv $TargetPath
        return
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv $TargetPath
        return
    }
    throw "Python 3.12 was not found. Install Python 3.12 and rerun scripts\\bootstrap-local.ps1."
}

function Prompt-Choice {
    param(
        [string]$Message,
        [string[]]$Options,
        [int]$DefaultIndex = 0
    )

    Write-Host ""
    Write-Host $Message
    for ($i = 0; $i -lt $Options.Count; $i++) {
        $suffix = if ($i -eq $DefaultIndex) { " (default)" } else { "" }
        Write-Host ("[{0}] {1}{2}" -f ($i + 1), $Options[$i], $suffix)
    }

    while ($true) {
        $raw = Read-Host -Prompt "Choose 1-$($Options.Count)"
        if ([string]::IsNullOrWhiteSpace($raw)) {
            return $Options[$DefaultIndex]
        }
        $index = 0
        if ([int]::TryParse($raw, [ref]$index) -and $index -ge 1 -and $index -le $Options.Count) {
            return $Options[$index - 1]
        }
        Write-Host "Please enter a number between 1 and $($Options.Count)." -ForegroundColor Yellow
    }
}

function Prompt-Value {
    param(
        [string]$Message,
        [string]$Default = "",
        [switch]$AllowEmpty,
        [switch]$Secret
    )

    while ($true) {
        $prompt = if ([string]::IsNullOrWhiteSpace($Default)) { $Message } else { "$Message [$Default]" }
        if ($Secret) {
            $secureValue = Read-Host -Prompt $prompt -AsSecureString
            $value = [System.Net.NetworkCredential]::new("", $secureValue).Password
        }
        else {
            $value = Read-Host -Prompt $prompt
        }
        if ([string]::IsNullOrWhiteSpace($value)) {
            $value = $Default
        }
        if ($AllowEmpty -or -not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
        Write-Host "A value is required." -ForegroundColor Yellow
    }
}

function Build-DatabaseUrl {
    param(
        [string]$DatabaseHost,
        [string]$DatabasePort,
        [string]$DatabaseName,
        [string]$DatabaseUser,
        [string]$DatabasePassword
    )

    $escapedUser = [System.Uri]::EscapeDataString($DatabaseUser)
    $escapedPassword = [System.Uri]::EscapeDataString($DatabasePassword)
    return "postgresql+psycopg://$escapedUser`:$escapedPassword@$DatabaseHost`:$DatabasePort/$DatabaseName"
}

function Write-DotEnv {
    param(
        [string]$Path,
        [string]$AppName,
        [string]$Environment,
        [string]$ApiPrefix,
        [string]$DatabaseUrl,
        [string]$ProfileStorePath
    )

    $lines = @(
        "APP_NAME=$AppName",
        "ENVIRONMENT=$Environment",
        "API_PREFIX=$ApiPrefix",
        "DATABASE_URL=$DatabaseUrl",
        "ENABLE_PGVECTOR=true",
        "PROFILE_STORE_PATH=$ProfileStorePath"
    )
    $lines | Set-Content -Path $Path -Encoding UTF8
}

function Initialize-PostgresDatabase {
    param(
        [string]$PythonPath,
        [string]$DatabaseHost,
        [string]$DatabasePort,
        [string]$DatabaseName,
        [string]$DatabaseUser,
        [string]$DatabasePassword,
        [string]$BootstrapDatabase
    )

    $env:FINKERNEL_DB_HOST = $DatabaseHost
    $env:FINKERNEL_DB_PORT = $DatabasePort
    $env:FINKERNEL_DB_NAME = $DatabaseName
    $env:FINKERNEL_DB_USER = $DatabaseUser
    $env:FINKERNEL_DB_PASSWORD = $DatabasePassword
    $env:FINKERNEL_DB_BOOTSTRAP = $BootstrapDatabase

    @'
import os

import psycopg
from psycopg import sql

host = os.environ["FINKERNEL_DB_HOST"]
port = os.environ["FINKERNEL_DB_PORT"]
dbname = os.environ["FINKERNEL_DB_NAME"]
user = os.environ["FINKERNEL_DB_USER"]
password = os.environ["FINKERNEL_DB_PASSWORD"]
bootstrap_db = os.environ["FINKERNEL_DB_BOOTSTRAP"]

admin_dsn = f"host={host} port={port} dbname={bootstrap_db} user={user} password={password}"
target_dsn = f"host={host} port={port} dbname={dbname} user={user} password={password}"

with psycopg.connect(admin_dsn, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        exists = cur.fetchone() is not None
        if not exists:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))

with psycopg.connect(target_dsn, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

print("PostgreSQL database and vector extension are ready.")
'@ | & $PythonPath -
}

function Write-McpConfigs {
    param(
        [string]$RepoRoot,
        [string]$PythonPath
    )

    $configDir = Join-Path $RepoRoot "config"
    Ensure-Directory -Path $configDir

    $httpConfigPath = Join-Path $configDir "host-agent-mcp-http.local.json"
    $stdioConfigPath = Join-Path $configDir "host-agent-mcp-stdio.local.json"

    $httpConfig = @{
        mcpServers = @{
            finkernel = @{
                type = "streamable-http"
                url = "http://localhost:8000/api/mcp/"
            }
        }
    }

    $stdioConfig = @{
        mcpServers = @{
            finkernel = @{
                command = $PythonPath
                args = @(
                    "-m",
                    "finkernel.transport.mcp.stdio_runner"
                )
                cwd = $RepoRoot
            }
        }
    }

    $httpConfig | ConvertTo-Json -Depth 8 | Set-Content -Path $httpConfigPath -Encoding UTF8
    $stdioConfig | ConvertTo-Json -Depth 8 | Set-Content -Path $stdioConfigPath -Encoding UTF8

    return @{
        Http = $httpConfigPath
        Stdio = $stdioConfigPath
    }
}

function Write-AgentBundle {
    param(
        [string]$RepoRoot,
        [string]$TargetDirectory,
        [string]$HttpConfigPath,
        [string]$StdioConfigPath
    )

    $bundleRoot = Join-Path $TargetDirectory "finkernel-agent"
    $bundlePromptDir = Join-Path $bundleRoot "prompts"
    Ensure-Directory -Path $bundlePromptDir

    Copy-Item $HttpConfigPath (Join-Path $bundleRoot "host-agent-mcp-http.json") -Force
    Copy-Item $StdioConfigPath (Join-Path $bundleRoot "host-agent-mcp-stdio.json") -Force
    Copy-Item (Join-Path $RepoRoot "SKILL.md") (Join-Path $bundleRoot "SKILL.md") -Force
    Copy-Item (Join-Path $RepoRoot "prompts\\*.md") $bundlePromptDir -Force

    $bundleReadme = @"
FinKernel agent bundle

- host-agent-mcp-http.json: HTTP MCP registration
- host-agent-mcp-stdio.json: local stdio MCP registration
- SKILL.md: top-level host skill
- prompts\\: full FinKernel routing + persona prompt pack
"@
    $bundleReadme | Set-Content -Path (Join-Path $bundleRoot "README.txt") -Encoding UTF8

    return $bundleRoot
}

function Get-AgentBundleDefaultDirectory {
    param(
        [string]$AgentChoice,
        [string]$RepoRoot
    )

    switch ($AgentChoice) {
        "Codex" {
            return Join-Path $HOME ".codex\\skills"
        }
        "Claude Code" {
            return Join-Path $HOME ".claude\\skills"
        }
        "OpenClaw" {
            return Join-Path $HOME ".openclaw\\skills"
        }
        "Hermes" {
            return Join-Path $HOME ".hermes\\skills"
        }
        "Custom MCP client" {
            return Join-Path $RepoRoot "integration\\custom-mcp-client"
        }
        default {
            return Join-Path $RepoRoot ("integration\\" + $AgentChoice.ToLower().Replace(" ", "-"))
        }
    }
}

function Get-AgentBundlePromptMessage {
    param(
        [string]$AgentChoice
    )

    switch ($AgentChoice) {
        "Codex" {
            return "Target parent directory for Codex skill installation"
        }
        "Claude Code" {
            return "Target parent directory for Claude Code skill installation"
        }
        "OpenClaw" {
            return "Target parent directory for OpenClaw skill installation"
        }
        "Hermes" {
            return "Target parent directory for Hermes skill installation"
        }
        "Custom MCP client" {
            return "Target directory for exported MCP configs and skill bundle"
        }
        default {
            return "Target directory for injected prompts/skill/config bundle"
        }
    }
}

function Register-CodexMcp {
    param(
        [string]$McpUrl
    )

    if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
        Write-Host "Codex CLI was not found. Skipping automatic Codex registration." -ForegroundColor Yellow
        return $false
    }

    try {
        & codex mcp add finkernel --url $McpUrl
        return $true
    }
    catch {
        Write-Host "Codex MCP registration failed: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

function Register-ClaudeCodeMcp {
    param(
        [string]$McpUrl
    )

    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        Write-Host "Claude Code CLI was not found. Skipping automatic Claude Code registration." -ForegroundColor Yellow
        return $false
    }

    try {
        & claude mcp add --transport http finkernel --scope local $McpUrl
        return $true
    }
    catch {
        Write-Host "Claude Code MCP registration failed: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

function Register-OpenClawMcp {
    param(
        [string]$McpUrl
    )

    if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
        Write-Host "OpenClaw CLI was not found. Skipping automatic OpenClaw registration." -ForegroundColor Yellow
        return $false
    }

    try {
        $serverDefinition = @{
            url = $McpUrl
            transport = "streamable-http"
        } | ConvertTo-Json -Compress

        & openclaw mcp set finkernel $serverDefinition
        return $true
    }
    catch {
        Write-Host "OpenClaw MCP registration failed: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

function Register-HermesMcp {
    param(
        [string]$McpUrl
    )

    if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
        Write-Host "Hermes CLI was not found. Skipping automatic Hermes registration." -ForegroundColor Yellow
        return $false
    }

    try {
        & hermes config set mcp_servers.finkernel.url $McpUrl
        return $true
    }
    catch {
        Write-Host "Hermes MCP registration failed: $($_.Exception.Message)" -ForegroundColor Yellow
        return $false
    }
}

function Register-AgentMcp {
    param(
        [string]$AgentChoice,
        [string]$McpUrl
    )

    switch ($AgentChoice) {
        "Codex" {
            return @{
                Registered = Register-CodexMcp -McpUrl $McpUrl
                Label = "Codex MCP registration"
                SuccessMessage = "FinKernel was registered with codex mcp add."
            }
        }
        "Claude Code" {
            return @{
                Registered = Register-ClaudeCodeMcp -McpUrl $McpUrl
                Label = "Claude Code MCP registration"
                SuccessMessage = "FinKernel was registered with claude mcp add."
            }
        }
        "OpenClaw" {
            return @{
                Registered = Register-OpenClawMcp -McpUrl $McpUrl
                Label = "OpenClaw MCP registration"
                SuccessMessage = "FinKernel was saved into the OpenClaw MCP registry."
            }
        }
        "Hermes" {
            return @{
                Registered = Register-HermesMcp -McpUrl $McpUrl
                Label = "Hermes MCP registration"
                SuccessMessage = "FinKernel was written into ~/.hermes/config.yaml."
            }
        }
        default {
            return $null
        }
    }
}

function Start-FinKernelApp {
    param(
        [string]$RepoRoot
    )

    $runScript = Join-Path $RepoRoot "scripts\\run-local.ps1"
    Start-Process powershell -WorkingDirectory $RepoRoot -ArgumentList @(
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $runScript
    ) | Out-Null
}

$repoRoot = Resolve-RepoRoot
Set-Location $repoRoot

$venvDir = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\\python.exe"
if (-not (Test-Path $venvPython)) {
    New-LocalVenv -TargetPath $venvDir
}

if (-not $SkipInstall) {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e ".[dev]"
}

$envPath = Join-Path $repoRoot ".env"
$writeEnv = $true
if (Test-Path $envPath) {
    $envChoice = Prompt-Choice -Message "An existing .env file was found. What should the installer do?" -Options @("Keep existing .env", "Rewrite .env interactively") -DefaultIndex 0
    $writeEnv = $envChoice -eq "Rewrite .env interactively"
}

$appName = "FinKernel"
$environment = "development"
$apiPrefix = "/api"
$databaseHost = "localhost"
$databasePort = "5432"
$databaseName = "finkernel"
$databaseUser = "finkernel"
$databasePassword = "change-me"
$bootstrapDatabase = "postgres"
$profileStorePath = "config/persona-profiles.json"

if ($writeEnv) {
    Write-Host ""
    Write-Host "FinKernel local setup targets PostgreSQL with the vector extension." -ForegroundColor Cyan
    $appName = Prompt-Value -Message "APP_NAME" -Default $appName
    $environment = Prompt-Value -Message "ENVIRONMENT" -Default $environment
    $apiPrefix = Prompt-Value -Message "API_PREFIX" -Default $apiPrefix
    $databaseHost = Prompt-Value -Message "PostgreSQL host" -Default $databaseHost
    $databasePort = Prompt-Value -Message "PostgreSQL port" -Default $databasePort
    $databaseName = Prompt-Value -Message "FinKernel database name" -Default $databaseName
    $databaseUser = Prompt-Value -Message "PostgreSQL user" -Default $databaseUser
    $databasePassword = Prompt-Value -Message "PostgreSQL password" -Default $databasePassword -Secret
    $bootstrapDatabase = Prompt-Value -Message "Bootstrap database to connect to before creating $databaseName" -Default $bootstrapDatabase
    $profileStorePath = Prompt-Value -Message "PROFILE_STORE_PATH" -Default $profileStorePath

    $databaseUrl = Build-DatabaseUrl `
        -DatabaseHost $databaseHost `
        -DatabasePort $databasePort `
        -DatabaseName $databaseName `
        -DatabaseUser $databaseUser `
        -DatabasePassword $databasePassword

    Write-DotEnv `
        -Path $envPath `
        -AppName $appName `
        -Environment $environment `
        -ApiPrefix $apiPrefix `
        -DatabaseUrl $databaseUrl `
        -ProfileStorePath $profileStorePath

    Initialize-PostgresDatabase `
        -PythonPath $venvPython `
        -DatabaseHost $databaseHost `
        -DatabasePort $databasePort `
        -DatabaseName $databaseName `
        -DatabaseUser $databaseUser `
        -DatabasePassword $databasePassword `
        -BootstrapDatabase $bootstrapDatabase
}

$profileSeedPath = Join-Path $repoRoot "config\\persona-profiles.json"
if (-not (Test-Path $profileSeedPath)) {
    Copy-Item (Join-Path $repoRoot "config\\persona-profiles.example.json") $profileSeedPath
}

$configPaths = Write-McpConfigs -RepoRoot $repoRoot -PythonPath $venvPython

$agentChoice = Prompt-Choice -Message "Which host agent should FinKernel integrate with?" -Options @("Codex", "Claude Code", "OpenClaw", "Hermes", "Custom MCP client", "Skip agent integration") -DefaultIndex 0
$bundleRoot = $null
$registrationResult = $null

if ($agentChoice -ne "Skip agent integration") {
    $bundleDefault = Get-AgentBundleDefaultDirectory -AgentChoice $agentChoice -RepoRoot $repoRoot
    $bundlePrompt = Get-AgentBundlePromptMessage -AgentChoice $agentChoice
    $bundleDir = Prompt-Value -Message $bundlePrompt -Default $bundleDefault
    Ensure-Directory -Path $bundleDir
    $bundleRoot = Write-AgentBundle `
        -RepoRoot $repoRoot `
        -TargetDirectory $bundleDir `
        -HttpConfigPath $configPaths.Http `
        -StdioConfigPath $configPaths.Stdio

    if (-not $SkipAgentRegistration) {
        $registrationResult = Register-AgentMcp -AgentChoice $agentChoice -McpUrl "http://localhost:8000/api/mcp/"
    }
}

$startNow = Prompt-Choice -Message "Start FinKernel now so the MCP endpoint is immediately available?" -Options @("Yes", "No") -DefaultIndex 0
if ($startNow -eq "Yes") {
    Start-FinKernelApp -RepoRoot $repoRoot
}

Write-Host ""
Write-Host "FinKernel bootstrap complete." -ForegroundColor Green
Write-Host ""
Write-Host "Environment:"
Write-Host "  .env -> $envPath"
Write-Host "  profile seed -> $profileSeedPath"
Write-Host ""
Write-Host "MCP configs:"
Write-Host "  HTTP  -> $($configPaths.Http)"
Write-Host "  stdio -> $($configPaths.Stdio)"
Write-Host ""
if ($bundleRoot) {
    Write-Host "Injected agent bundle:"
    Write-Host "  $bundleRoot"
    Write-Host ""
}
if ($registrationResult -and $registrationResult.Registered) {
    Write-Host "$($registrationResult.Label):"
    Write-Host "  $($registrationResult.SuccessMessage)"
    Write-Host ""
}
Write-Host "Run FinKernel locally with:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\\scripts\\run-local.ps1"
