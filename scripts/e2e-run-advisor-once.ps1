param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$ProfileId = "growth"
)

$uri = "$BaseUrl/api/advisor/run-once?profile_id=$ProfileId"

Write-Host "Running advisor loop once for profile $ProfileId"

$response = Invoke-RestMethod `
    -Method Post `
    -Uri $uri

Write-Host ""
Write-Host "Advisor run complete."
Write-Host "Created suggestions: $($response.created_suggestions)"
Write-Host "Total strategies scanned: $($response.total_strategies)"
Write-Host ""

$response | ConvertTo-Json -Depth 10
