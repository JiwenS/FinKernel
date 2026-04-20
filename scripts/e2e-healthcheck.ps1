param(
    [string]$BaseUrl = "http://localhost:8000",
    [int]$TimeoutSeconds = 120
)

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$healthUrl = "$BaseUrl/api/health"

Write-Host "Waiting for FinKernel health endpoint: $healthUrl"

while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-RestMethod -Method Get -Uri $healthUrl -TimeoutSec 5
        Write-Host "FinKernel is healthy."
        $response | ConvertTo-Json -Depth 5
        exit 0
    } catch {
        Start-Sleep -Seconds 2
    }
}

Write-Error "FinKernel did not become healthy within $TimeoutSeconds seconds."
exit 1
