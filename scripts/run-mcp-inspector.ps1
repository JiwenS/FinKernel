param(
    [string]$ConfigPath = "config/mcp-inspector.json",
    [string]$ServerName = "finkernel",
    [int]$ClientPort = 6274,
    [int]$ServerPort = 6277,
    [switch]$Cli,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

function Test-PortAvailable {
    param([int]$Port)

    $activePorts = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners().Port
    return ($Port -notin $activePorts)
}

function Get-AvailablePort {
    param([int]$PreferredPort)

    $port = $PreferredPort
    while (-not (Test-PortAvailable -Port $port)) {
        $port += 1
    }
    return $port
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$inspector = Join-Path $repoRoot "node_modules/.bin/mcp-inspector.cmd"

if (-not (Test-Path $inspector)) {
    Write-Error "MCP Inspector is not installed. Run 'npm install' in $repoRoot first."
    exit 1
}

$resolvedConfigPath = if ([System.IO.Path]::IsPathRooted($ConfigPath)) {
    $ConfigPath
} else {
    Join-Path $repoRoot $ConfigPath
}

if ($Cli) {
    $cliBuildDir = Join-Path $repoRoot "node_modules/@modelcontextprotocol/inspector-cli/build"

    if (-not (Test-Path $cliBuildDir)) {
        Write-Error "Missing Inspector CLI build directory: $cliBuildDir"
        exit 1
    }

    $config = Get-Content $resolvedConfigPath | ConvertFrom-Json
    $server = $config.mcpServers.$ServerName

    if ($null -eq $server) {
        Write-Error "Server '$ServerName' was not found in $resolvedConfigPath."
        exit 1
    }

    $cliArgs = @()

    if ($server.type -eq "streamable-http") {
        $cliArgs += $server.url
        $cliArgs += "--transport"
        $cliArgs += "http"
    } elseif ($server.type -eq "sse") {
        $cliArgs += $server.url
        $cliArgs += "--transport"
        $cliArgs += "sse"
    } else {
        Write-Error "CLI helper currently supports streamable-http and sse config entries only."
        exit 1
    }

    if ($ExtraArgs) {
        $cliArgs += $ExtraArgs
    }

    Push-Location $cliBuildDir
    try {
        & node ".\index.js" @cliArgs
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
} else {
    $selectedClientPort = Get-AvailablePort -PreferredPort $ClientPort
    $selectedServerPort = Get-AvailablePort -PreferredPort $ServerPort

    if ($selectedServerPort -eq $selectedClientPort) {
        $selectedServerPort = Get-AvailablePort -PreferredPort ($selectedClientPort + 1)
    }

    if ($selectedClientPort -ne $ClientPort) {
        Write-Host "Client port $ClientPort is busy, using $selectedClientPort instead."
    }

    if ($selectedServerPort -ne $ServerPort) {
        Write-Host "Proxy port $ServerPort is busy, using $selectedServerPort instead."
    }

    Write-Host "Starting MCP inspector..."
    Write-Host "Inspector UI: http://localhost:$selectedClientPort"
    Write-Host "Inspector proxy: http://localhost:$selectedServerPort"

    $env:CLIENT_PORT = "$selectedClientPort"
    $env:SERVER_PORT = "$selectedServerPort"
    $args = @("--config", $resolvedConfigPath, "--server", $ServerName)

    if ($ExtraArgs) {
        $args += $ExtraArgs
    }

    & $inspector @args
    $exitCode = $LASTEXITCODE
}

if ($null -ne $exitCode) {
    exit $exitCode
}
