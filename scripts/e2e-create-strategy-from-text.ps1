param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$ProfileId = "growth",
    [string]$Text = "我有 20k 的模拟资金，想做成长型投资，重点关注 AAPL、MSFT、NVDA。"
)

$uri = "$BaseUrl/api/strategies/from-text"

$body = @{
    text = $Text
    auto_activate = $true
} | ConvertTo-Json -Depth 10

Write-Host "Creating strategy from text for profile $ProfileId"

$response = Invoke-RestMethod `
    -Method Post `
    -Uri $uri `
    -Headers @{ "x-profile-id" = $ProfileId } `
    -ContentType "application/json" `
    -Body $body

Write-Host ""
Write-Host "Strategy created from text."
Write-Host "Strategy ID: $($response.strategy.strategy_id)"
Write-Host "Detected style: $($response.interpretation.detected_style)"
Write-Host ""

$response | ConvertTo-Json -Depth 12
