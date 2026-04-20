param(
    [Parameter(Mandatory = $true)]
    [string]$RequestId,
    [string]$ProfileId = "growth",
    [string]$BaseUrl = "http://localhost:8000"
)

$uri = "$BaseUrl/api/trade-requests/$RequestId"

Write-Host "Fetching trade request: $RequestId"
$response = Invoke-RestMethod -Method Get -Uri $uri -Headers @{ "x-profile-id" = $ProfileId }
$response | ConvertTo-Json -Depth 5
