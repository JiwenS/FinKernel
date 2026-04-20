param(
    [string]$ConfigPath = "config/mcp-inspector.json",
    [string]$ServerName = "finkernel"
)

$launcher = Join-Path $PSScriptRoot "run-mcp-inspector.ps1"

if (-not (Test-Path $launcher)) {
    Write-Error "Missing launcher script: $launcher"
    exit 1
}

& $launcher -Cli -ConfigPath $ConfigPath -ServerName $ServerName --method tools/list
$exitCode = $LASTEXITCODE
if ($null -ne $exitCode) {
    exit $exitCode
}
