# Test the new /llm/steps endpoint on LLM service (port 8002)

Write-Host "Testing /llm/steps endpoint on LLM service..." -ForegroundColor Cyan
Write-Host ""

# Test 1: Generate only (execute=false)
Write-Host "=== Test 1: Generate Only (execute=false) ===" -ForegroundColor Yellow
$body1 = @{
    instruction = "Open Chrome browser"
    model = "mistral"
    execute = $false
} | ConvertTo-Json

Write-Host "Calling: POST http://localhost:8002/llm/steps" -ForegroundColor Gray
$response1 = Invoke-WebRequest -Uri http://localhost:8002/llm/steps `
    -Method POST `
    -ContentType "application/json" `
    -Body $body1 `
    -UseBasicParsing

Write-Host "Status: $($response1.StatusCode)" -ForegroundColor Green
Write-Host "Response:" -ForegroundColor Gray
$response1.Content | ConvertFrom-Json | ConvertTo-Json -Depth 5
Write-Host ""
Write-Host ""

# Test 2: Generate and Execute (execute=true)
Write-Host "=== Test 2: Generate and Execute (execute=true) ===" -ForegroundColor Yellow
Write-Host "⚠️  WARNING: This will actually execute the steps!" -ForegroundColor Red
Write-Host ""

$body2 = @{
    instruction = "Open Chrome browser"
    model = "mistral"
    execute = $true
} | ConvertTo-Json

Write-Host "Calling: POST http://localhost:8002/llm/steps" -ForegroundColor Gray
try {
    $response2 = Invoke-WebRequest -Uri http://localhost:8002/llm/steps `
        -Method POST `
        -ContentType "application/json" `
        -Body $body2 `
        -UseBasicParsing

    Write-Host "Status: $($response2.StatusCode)" -ForegroundColor Green
    Write-Host "Response:" -ForegroundColor Gray
    $response2.Content | ConvertFrom-Json | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        $reader.BaseStream.Position = 0
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response Body: $responseBody" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Testing complete!" -ForegroundColor Cyan
