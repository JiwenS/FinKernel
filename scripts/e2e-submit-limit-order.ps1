param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$ProfileId = "growth",
    [string]$UserId = "local-e2e-user",
    [string]$AccountId = "paper-account-1",
    [string]$Symbol = "AAPL",
    [ValidateSet("buy", "sell")]
    [string]$Side = "buy",
    [int]$Quantity = 1,
    [decimal]$LimitPrice = 100.00,
    [string]$RequestSource = "powershell-e2e"
)

$idempotencyKey = [guid]::NewGuid().ToString()
$uri = "$BaseUrl/api/trade-requests"

$body = @{
    actor = @{
        user_id = $UserId
        account_id = $AccountId
    }
    symbol = $Symbol
    side = $Side
    quantity = $Quantity
    limit_price = $LimitPrice.ToString("0.00")
    idempotency_key = $idempotencyKey
} | ConvertTo-Json -Depth 5

Write-Host "Submitting limit order request to $uri"

$response = Invoke-RestMethod `
    -Method Post `
    -Uri $uri `
    -Headers @{ "x-request-source" = $RequestSource; "x-profile-id" = $ProfileId } `
    -ContentType "application/json" `
    -Body $body

Write-Host ""
Write-Host "Trade request created."
Write-Host "Request ID: $($response.request_id)"
Write-Host "State: $($response.state)"
Write-Host "Policy decision: $($response.policy_decision)"
Write-Host "Request source: $($response.request_source)"
Write-Host ""
Write-Host "Next step:"
Write-Host "1. Check your Discord HITL channel for the approval message."
Write-Host "2. Copy the token from the Discord message."
Write-Host "3. Approve with:"
Write-Host "   !approve $($response.request_id) <token>"
Write-Host ""

$response | ConvertTo-Json -Depth 5
