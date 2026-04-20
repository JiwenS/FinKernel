param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$ProfileId = "growth",
    [string]$Status = ""
)

$uri = "$BaseUrl/api/suggestions"
if ($Status) {
    $uri = "$uri?status=$Status"
}

Write-Host "Fetching suggestions for profile $ProfileId"

$response = Invoke-RestMethod `
    -Method Get `
    -Uri $uri `
    -Headers @{ "x-profile-id" = $ProfileId }

$response | ConvertTo-Json -Depth 12
