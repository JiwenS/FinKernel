param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$ProfileId = "growth",
    [string]$Name = "Growth Rebalance",
    [string]$MandateSummary = "Move the profile toward the configured target allocation.",
    [decimal]$RebalanceThresholdPct = 0.05
)

$uri = "$BaseUrl/api/strategies"

$body = @{
    name = $Name
    mandate_summary = $MandateSummary
    target_allocation = @{
        AAPL = "0.80"
        MSFT = "0.10"
        NVDA = "0.10"
    }
    rebalance_threshold_pct = $RebalanceThresholdPct.ToString("0.00")
} | ConvertTo-Json -Depth 10

Write-Host "Creating advisor strategy at $uri"

$response = Invoke-RestMethod `
    -Method Post `
    -Uri $uri `
    -Headers @{ "x-profile-id" = $ProfileId } `
    -ContentType "application/json" `
    -Body $body

Write-Host ""
Write-Host "Strategy created."
Write-Host "Strategy ID: $($response.strategy_id)"
Write-Host "Profile ID: $($response.profile_id)"
Write-Host ""

$response | ConvertTo-Json -Depth 10
