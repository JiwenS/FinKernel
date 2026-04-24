param(
    [switch]$Yes,
    [switch]$KeepEnv,
    [switch]$KeepSeedData,
    [switch]$KeepAgentBundles,
    [switch]$SkipAgentUnregistration,
    [switch]$KeepDockerVolumes,
    [switch]$KeepLocalImage
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
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

function Confirm-Uninstall {
    if ($Yes) {
        return
    }

    $choice = Prompt-Choice -Message "This will remove the FinKernel Docker stack, generated local files, and host-side FinKernel profile bundles. Continue?" -Options @("No", "Yes") -DefaultIndex 0
    if ($choice -ne "Yes") {
        throw "Uninstall cancelled."
    }
}

function Get-DockerComposeMode {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return $null
    }

    try {
        & docker version *> $null
    }
    catch {
        return $null
    }

    try {
        & docker compose version *> $null
        return "plugin"
    }
    catch {
        if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
            return "legacy"
        }
        return $null
    }
}

function Invoke-DockerCompose {
    param(
        [string]$ComposeMode,
        [string[]]$ComposeArgs,
        [string]$RepoRoot
    )

    if (-not $ComposeMode) {
        Write-Host "Docker compose is not available. Skipping Docker stack removal." -ForegroundColor Yellow
        return $false
    }

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
        return $true
    }
    finally {
        Pop-Location
    }
}

function Read-InstallState {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return $null
    }

    return Get-Content -Path $Path -Raw | ConvertFrom-Json
}

function Get-NormalizedPath {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }

    return [System.IO.Path]::GetFullPath($Path)
}

function Remove-LocalFile {
    param(
        [string]$Path
    )

    $fullPath = Get-NormalizedPath -Path $Path
    if (-not $fullPath -or -not (Test-Path $fullPath)) {
        return $false
    }

    Remove-Item -LiteralPath $fullPath -Force
    return $true
}

function Remove-FinkernelBundleDirectory {
    param(
        [string]$Path
    )

    $fullPath = Get-NormalizedPath -Path $Path
    if (-not $fullPath -or -not (Test-Path $fullPath)) {
        return $false
    }

    $leaf = Split-Path -Leaf $fullPath
    if ($leaf -notin @("finkernel-profile", "finkernel-agent")) {
        Write-Host "Skipping unexpected bundle path: $fullPath" -ForegroundColor Yellow
        return $false
    }

    Remove-Item -LiteralPath $fullPath -Recurse -Force
    return $true
}

function Get-KnownBundleRoots {
    param(
        [string]$RepoRoot,
        $InstallState
    )

    $paths = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
        $InstallState.bundle_root,
        (Join-Path $HOME ".codex\\skills\\finkernel-profile"),
        (Join-Path $HOME ".claude\\skills\\finkernel-profile"),
        (Join-Path $HOME ".openclaw\\skills\\finkernel-profile"),
        (Join-Path $HOME ".hermes\\skills\\finkernel-profile"),
        (Join-Path $RepoRoot "integration\\custom-mcp-client\\finkernel-profile"),
        (Join-Path $HOME ".codex\\skills\\finkernel-agent"),
        (Join-Path $HOME ".claude\\skills\\finkernel-agent"),
        (Join-Path $HOME ".openclaw\\skills\\finkernel-agent"),
        (Join-Path $HOME ".hermes\\skills\\finkernel-agent"),
        (Join-Path $RepoRoot "integration\\custom-mcp-client\\finkernel-agent")
    )) {
        $normalized = Get-NormalizedPath -Path $candidate
        if ($normalized -and -not $paths.Contains($normalized)) {
            $paths.Add($normalized)
        }
    }

    return $paths
}

function Remove-TomlTableBlock {
    param(
        [string]$Path,
        [string]$Header
    )

    if (-not (Test-Path $Path)) {
        return $false
    }

    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($line in Get-Content -Path $Path) {
        $lines.Add($line)
    }

    $start = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -eq $Header) {
            $start = $i
            break
        }
    }
    if ($start -lt 0) {
        return $false
    }

    $end = $lines.Count
    for ($i = $start + 1; $i -lt $lines.Count; $i++) {
        if ($lines[$i].TrimStart().StartsWith("[")) {
            $end = $i
            break
        }
    }

    $count = $end - $start
    $lines.RemoveRange($start, $count)

    while ($start -gt 0 -and $start -lt $lines.Count) {
        if ([string]::IsNullOrWhiteSpace($lines[$start - 1]) -and [string]::IsNullOrWhiteSpace($lines[$start])) {
            $lines.RemoveAt($start)
            continue
        }
        break
    }

    $lines | Set-Content -Path $Path -Encoding UTF8
    return $true
}

function Unregister-CodexMcp {
    $configPath = Join-Path $HOME ".codex\\config.toml"
    return Remove-TomlTableBlock -Path $configPath -Header "[mcp_servers.finkernel]"
}

function Unregister-ClaudeCodeMcp {
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        return $false
    }

    try {
        & claude mcp remove finkernel *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Unregister-OpenClawMcp {
    if (-not (Get-Command openclaw -ErrorAction SilentlyContinue)) {
        return $false
    }

    try {
        & openclaw mcp unset finkernel *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Remove-HermesFinkernelConfig {
    $configPath = Join-Path $HOME ".hermes\\config.yaml"
    if (-not (Test-Path $configPath)) {
        return $false
    }

    $lines = Get-Content -Path $configPath
    $rootIndex = -1
    $rootIndent = 0
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^(\s*)mcp_servers:\s*$') {
            $rootIndex = $i
            $rootIndent = $Matches[1].Length
            break
        }
    }
    if ($rootIndex -lt 0) {
        return $false
    }

    $rootEnd = $lines.Count
    for ($i = $rootIndex + 1; $i -lt $lines.Count; $i++) {
        $trimmed = $lines[$i].Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $indent = ($lines[$i].Length - $lines[$i].TrimStart().Length)
        if ($indent -le $rootIndent) {
            $rootEnd = $i
            break
        }
    }

    $targetIndex = -1
    $targetIndent = 0
    for ($i = $rootIndex + 1; $i -lt $rootEnd; $i++) {
        if ($lines[$i] -match '^(\s*)finkernel:\s*$') {
            $targetIndex = $i
            $targetIndent = $Matches[1].Length
            break
        }
    }
    if ($targetIndex -lt 0) {
        return $false
    }

    $targetEnd = $rootEnd
    for ($i = $targetIndex + 1; $i -lt $rootEnd; $i++) {
        $trimmed = $lines[$i].Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $indent = ($lines[$i].Length - $lines[$i].TrimStart().Length)
        if ($indent -le $targetIndent) {
            $targetEnd = $i
            break
        }
    }

    $remainingChild = $false
    for ($i = $rootIndex + 1; $i -lt $rootEnd; $i++) {
        if ($i -ge $targetIndex -and $i -lt $targetEnd) {
            continue
        }
        $trimmed = $lines[$i].Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $indent = ($lines[$i].Length - $lines[$i].TrimStart().Length)
        if ($indent -gt $rootIndent) {
            $remainingChild = $true
            break
        }
    }

    $result = [System.Collections.Generic.List[string]]::new()
    if ($remainingChild) {
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($i -lt $targetIndex -or $i -ge $targetEnd) {
                $result.Add($lines[$i])
            }
        }
    }
    else {
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($i -lt $rootIndex -or $i -ge $rootEnd) {
                $result.Add($lines[$i])
            }
        }
    }

    $result | Set-Content -Path $configPath -Encoding UTF8
    return $true
}

function Unregister-AgentMcp {
    param(
        [string]$AgentChoice
    )

    switch ($AgentChoice) {
        "Codex" {
            return @{
                Label = "Codex MCP registration"
                Removed = Unregister-CodexMcp
            }
        }
        "Claude Code" {
            return @{
                Label = "Claude Code MCP registration"
                Removed = Unregister-ClaudeCodeMcp
            }
        }
        "OpenClaw" {
            return @{
                Label = "OpenClaw MCP registration"
                Removed = Unregister-OpenClawMcp
            }
        }
        "Hermes" {
            return @{
                Label = "Hermes MCP registration"
                Removed = Remove-HermesFinkernelConfig
            }
        }
        default {
            return $null
        }
    }
}

$repoRoot = Resolve-RepoRoot
$statePath = Join-Path $repoRoot "config\\bootstrap-install-state.local.json"
$installState = Read-InstallState -Path $statePath

Confirm-Uninstall

$composeMode = Get-DockerComposeMode
$composeArgs = @("down", "--remove-orphans")
if (-not $KeepDockerVolumes) {
    $composeArgs += "-v"
}
if (-not $KeepLocalImage) {
    $composeArgs += @("--rmi", "local")
}
$dockerRemoved = Invoke-DockerCompose -ComposeMode $composeMode -ComposeArgs $composeArgs -RepoRoot $repoRoot

$removedFiles = [System.Collections.Generic.List[string]]::new()
$removedBundles = [System.Collections.Generic.List[string]]::new()
$removedRegistrations = [System.Collections.Generic.List[string]]::new()

if (-not $SkipAgentUnregistration) {
    $agentChoices = [System.Collections.Generic.List[string]]::new()
    foreach ($agent in @($installState.agent_choice, "Codex", "Claude Code", "OpenClaw", "Hermes")) {
        if ($agent -and $agent -ne "Custom MCP client" -and $agent -ne "Skip agent integration" -and -not $agentChoices.Contains($agent)) {
            $agentChoices.Add($agent)
        }
    }

    foreach ($agent in $agentChoices) {
        $result = Unregister-AgentMcp -AgentChoice $agent
        if ($result -and $result.Removed) {
            $removedRegistrations.Add($result.Label)
        }
    }
}

if (-not $KeepAgentBundles) {
    foreach ($bundleRoot in Get-KnownBundleRoots -RepoRoot $repoRoot -InstallState $installState) {
        if (Remove-FinkernelBundleDirectory -Path $bundleRoot) {
            $removedBundles.Add($bundleRoot)
        }
    }
}

foreach ($localPath in @(
    (Join-Path $repoRoot "config\\host-agent-mcp-http.local.json"),
    $statePath
)) {
    if (Remove-LocalFile -Path $localPath) {
        $removedFiles.Add((Get-NormalizedPath -Path $localPath))
    }
}

if (-not $KeepSeedData) {
    $seedPath = Join-Path $repoRoot "config\\persona-profiles.json"
    if (Remove-LocalFile -Path $seedPath) {
        $removedFiles.Add((Get-NormalizedPath -Path $seedPath))
    }
}

if (-not $KeepEnv) {
    $envPath = Join-Path $repoRoot ".env"
    if (Remove-LocalFile -Path $envPath) {
        $removedFiles.Add((Get-NormalizedPath -Path $envPath))
    }
}

Write-Host ""
Write-Host "FinKernel uninstall complete." -ForegroundColor Green
Write-Host ""
Write-Host "Docker cleanup:"
if ($dockerRemoved) {
    Write-Host "  Docker compose resources were removed."
}
else {
    Write-Host "  Docker cleanup was skipped."
}
Write-Host ""
Write-Host "Local files removed:"
if ($removedFiles.Count -eq 0) {
    Write-Host "  none"
}
else {
    foreach ($path in $removedFiles) {
        Write-Host "  $path"
    }
}
Write-Host ""
Write-Host "Agent bundles removed:"
if ($removedBundles.Count -eq 0) {
    Write-Host "  none"
}
else {
    foreach ($path in $removedBundles) {
        Write-Host "  $path"
    }
}
Write-Host ""
Write-Host "Agent MCP registrations removed:"
if ($removedRegistrations.Count -eq 0) {
    Write-Host "  none"
}
else {
    foreach ($label in $removedRegistrations) {
        Write-Host "  $label"
    }
}
