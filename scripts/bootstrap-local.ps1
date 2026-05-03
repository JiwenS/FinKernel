param(
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

function Get-DotEnvDefaults {
    return @{
        STORAGE_BACKEND = "database"
        PROFILE_DATA_DIR = ".finkernel"
        PROFILE_STORE_PATH = "config/persona-profiles.json"
        APP_PORT = "8000"
        POSTGRES_DB = "finkernel"
        POSTGRES_USER = "finkernel"
        POSTGRES_PASSWORD = "change-me"
    }
}

function Read-DotEnv {
    param(
        [string]$Path
    )

    $values = Get-DotEnvDefaults
    if (-not (Test-Path $Path)) {
        return $values
    }

    foreach ($line in Get-Content -Path $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($key) {
            $values[$key] = $value
        }
    }

    return $values
}

function Write-DotEnv {
    param(
        [string]$Path,
        [hashtable]$Values
    )

    $lines = @(
        "# Server-mode local settings for FinKernel",
        "STORAGE_BACKEND=database",
        "PROFILE_DATA_DIR=$($Values.PROFILE_DATA_DIR)",
        "PROFILE_STORE_PATH=$($Values.PROFILE_STORE_PATH)",
        "",
        "# Host port exposed by the FinKernel HTTP app.",
        "APP_PORT=$($Values.APP_PORT)",
        "",
        "# PostgreSQL credentials used by the compose-managed pgvector container.",
        "POSTGRES_DB=$($Values.POSTGRES_DB)",
        "POSTGRES_USER=$($Values.POSTGRES_USER)",
        "POSTGRES_PASSWORD=$($Values.POSTGRES_PASSWORD)"
    )
    $lines | Set-Content -Path $Path -Encoding UTF8
}

function Prompt-DotEnvValues {
    param(
        [hashtable]$CurrentValues
    )

    Write-Host ""
    Write-Host "FinKernel Server setup will configure Docker Compose, start PostgreSQL with pgvector, and then register host-agent MCP access." -ForegroundColor Cyan

    return @{
        APP_PORT = (Prompt-Value -Message "Host port for FinKernel HTTP and MCP" -Default $CurrentValues.APP_PORT)
        POSTGRES_DB = (Prompt-Value -Message "Docker PostgreSQL database name" -Default $CurrentValues.POSTGRES_DB)
        POSTGRES_USER = (Prompt-Value -Message "Docker PostgreSQL user" -Default $CurrentValues.POSTGRES_USER)
        POSTGRES_PASSWORD = (Prompt-Value -Message "Docker PostgreSQL password" -Default $CurrentValues.POSTGRES_PASSWORD -Secret)
    }
}

function Get-DockerComposeMode {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI was not found. Install Docker Desktop (or Docker Engine with docker compose) and rerun scripts\\bootstrap.ps1 -Mode Server."
    }

    try {
        & docker version *> $null
    }
    catch {
        throw "Docker is installed but not reachable. Start Docker and rerun scripts\\bootstrap.ps1 -Mode Server."
    }

    try {
        & docker compose version *> $null
        return "plugin"
    }
    catch {
        if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
            return "legacy"
        }
        throw "Docker compose was not found. Install a Docker version that includes docker compose and rerun scripts\\bootstrap.ps1 -Mode Server."
    }
}

function Invoke-DockerCompose {
    param(
        [string]$ComposeMode,
        [string[]]$ComposeArgs,
        [string]$RepoRoot
    )

    Push-Location $RepoRoot
    try {
        if ($ComposeMode -eq "legacy") {
            & docker-compose @ComposeArgs
        }
        else {
            & docker compose @ComposeArgs
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Docker compose command failed."
        }
    }
    finally {
        Pop-Location
    }
}

function Wait-ForHttpHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 180
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -Method Get -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                return
            }
        }
        catch {
        }
        Start-Sleep -Seconds 2
    }

    throw "FinKernel did not become healthy at $Url within $TimeoutSeconds seconds."
}

function Write-McpHttpConfig {
    param(
        [string]$RepoRoot,
        [string]$McpUrl
    )

    $configDir = Join-Path $RepoRoot "config"
    Ensure-Directory -Path $configDir

    $httpConfigPath = Join-Path $configDir "host-agent-mcp-http.local.json"

    $httpConfig = @{
        mcpServers = @{
            finkernel = @{
                type = "streamable-http"
                url = $McpUrl
            }
        }
    }

    $httpConfig | ConvertTo-Json -Depth 8 | Set-Content -Path $httpConfigPath -Encoding UTF8
    return $httpConfigPath
}

function Write-InstallState {
    param(
        [string]$RepoRoot,
        [hashtable]$State
    )

    $configDir = Join-Path $RepoRoot "config"
    Ensure-Directory -Path $configDir

    $statePath = Join-Path $configDir "bootstrap-install-state.local.json"
    $State | ConvertTo-Json -Depth 8 | Set-Content -Path $statePath -Encoding UTF8
    return $statePath
}

function Write-AgentBundle {
    param(
        [string]$RepoRoot,
        [string]$TargetDirectory,
        [string]$HttpConfigPath
    )

    $bundleRoot = Join-Path $TargetDirectory "finkernel-profile"
    $bundlePromptDir = Join-Path $bundleRoot "prompts"
    Ensure-Directory -Path $bundlePromptDir

    Copy-Item $HttpConfigPath (Join-Path $bundleRoot "host-agent-mcp-http.json") -Force
    Copy-Item (Join-Path $RepoRoot "SKILL.md") (Join-Path $bundleRoot "SKILL.md") -Force
    Copy-Item (Join-Path $RepoRoot "prompts\\*.md") $bundlePromptDir -Force

    $legacyBundleRoot = Join-Path $TargetDirectory "finkernel-agent"
    if (Test-Path $legacyBundleRoot) {
        Remove-Item -LiteralPath $legacyBundleRoot -Recurse -Force
    }

    $bundleReadme = @"
FinKernel profile skill bundle

- host-agent-mcp-http.json: HTTP MCP registration
- SKILL.md: FinKernel Profile skill
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
            return "Target directory for exported MCP HTTP config and skill bundle"
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

$repoRoot = Resolve-RepoRoot
Set-Location $repoRoot

$envPath = Join-Path $repoRoot ".env"
$envValues = Read-DotEnv -Path $envPath
$writeEnv = -not (Test-Path $envPath)

if (Test-Path $envPath) {
    $envChoice = Prompt-Choice -Message "An existing .env file was found. What should the installer do?" -Options @("Keep existing .env", "Rewrite .env interactively") -DefaultIndex 0
    $writeEnv = $envChoice -eq "Rewrite .env interactively"
}

if ($writeEnv) {
    $envValues = Prompt-DotEnvValues -CurrentValues $envValues
    Write-DotEnv -Path $envPath -Values $envValues
}

$profileStorePath = Join-Path $repoRoot "config\\persona-profiles.json"
if (-not (Test-Path $profileStorePath)) {
    Copy-Item (Join-Path $repoRoot "config\\persona-profiles.example.json") $profileStorePath
}

$composeMode = Get-DockerComposeMode
Invoke-DockerCompose -ComposeMode $composeMode -ComposeArgs @("up", "-d", "--build", "--remove-orphans") -RepoRoot $repoRoot

$appPort = $envValues.APP_PORT
$mcpUrl = "http://localhost:$appPort/api/mcp/"
Wait-ForHttpHealth -Url "http://localhost:$appPort/api/health" -TimeoutSeconds 180

$httpConfigPath = Write-McpHttpConfig -RepoRoot $repoRoot -McpUrl $mcpUrl

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
        -HttpConfigPath $httpConfigPath

    if (-not $SkipAgentRegistration) {
        $registrationResult = Register-AgentMcp -AgentChoice $agentChoice -McpUrl $mcpUrl
    }
}

$installStatePath = Write-InstallState -RepoRoot $repoRoot -State @{
    installed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    env_path = $envPath
    profile_store_path = $profileStorePath
    http_config_path = $httpConfigPath
    app_port = $appPort
    mcp_url = $mcpUrl
    agent_choice = $agentChoice
    bundle_root = $bundleRoot
    agent_registration_attempted = (-not $SkipAgentRegistration)
    agent_registration_succeeded = [bool]($registrationResult -and $registrationResult.Registered)
}

Write-Host ""
Write-Host "FinKernel bootstrap complete." -ForegroundColor Green
Write-Host ""
Write-Host "Environment:"
Write-Host "  .env -> $envPath"
Write-Host "  profile store -> $profileStorePath"
Write-Host ""
Write-Host "Docker services:"
Write-Host "  FinKernel health -> http://localhost:$appPort/api/health"
Write-Host "  FinKernel MCP    -> $mcpUrl"
Write-Host ""
Write-Host "MCP config:"
Write-Host "  HTTP -> $httpConfigPath"
Write-Host ""
Write-Host "Install manifest:"
Write-Host "  $installStatePath"
Write-Host ""
if ($bundleRoot) {
    Write-Host "Injected profile skill bundle:"
    Write-Host "  $bundleRoot"
    Write-Host ""
}
if ($registrationResult -and $registrationResult.Registered) {
    Write-Host "$($registrationResult.Label):"
    Write-Host "  $($registrationResult.SuccessMessage)"
    Write-Host ""
}
Write-Host "Restart the Docker stack later with:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\\scripts\\run-local.ps1"
