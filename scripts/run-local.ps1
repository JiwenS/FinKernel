param(
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-DotEnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Default = ""
    )

    if (-not (Test-Path $Path)) {
        return $Default
    }

    foreach ($line in Get-Content -Path $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $parts = $trimmed -split "=", 2
        if ($parts.Count -eq 2 -and $parts[0].Trim() -eq $Key) {
            return $parts[1].Trim()
        }
    }

    return $Default
}

function Get-DockerComposeCommand {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI was not found. Install Docker Desktop (or Docker Engine with docker compose) and rerun scripts\\run-local.ps1."
    }

    try {
        & docker version | Out-Null
    }
    catch {
        throw "Docker is installed but not reachable. Start Docker and rerun scripts\\run-local.ps1."
    }

    try {
        & docker compose version | Out-Null
        return @("docker", "compose")
    }
    catch {
        if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
            return @("docker-compose")
        }
        throw "Docker compose was not found. Install a Docker version that includes docker compose and rerun scripts\\run-local.ps1."
    }
}

function Invoke-DockerCompose {
    param(
        [string[]]$ComposeCommand,
        [string[]]$Args,
        [string]$RepoRoot
    )

    Push-Location $RepoRoot
    try {
        if ($ComposeCommand.Count -eq 1) {
            & $ComposeCommand[0] @Args
        }
        else {
            & $ComposeCommand[0] $ComposeCommand[1] @Args
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

$repoRoot = Resolve-RepoRoot
$envPath = Join-Path $repoRoot ".env"
if (-not (Test-Path $envPath)) {
    throw "Missing .env at $envPath. Run scripts\\bootstrap-local.ps1 first."
}

$appPort = Get-DotEnvValue -Path $envPath -Key "APP_PORT" -Default "8000"
$composeCommand = Get-DockerComposeCommand

Invoke-DockerCompose -ComposeCommand $composeCommand -Args @("up", "-d", "--build", "--remove-orphans") -RepoRoot $repoRoot
Wait-ForHttpHealth -Url "http://localhost:$appPort/api/health" -TimeoutSeconds $TimeoutSeconds

Write-Host ""
Write-Host "FinKernel Docker stack is running." -ForegroundColor Green
Write-Host "Health endpoint:"
Write-Host "  http://localhost:$appPort/api/health"
Write-Host "MCP endpoint:"
Write-Host "  http://localhost:$appPort/api/mcp/"
