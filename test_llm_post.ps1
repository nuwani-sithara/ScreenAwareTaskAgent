$body = @{
    instruction = "Open Chrome browser"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8002/llm/generate `
    -Method POST `
    -ContentType "application/json" `
    -Body $body `
    -UseBasicParsing | Out-Null

Write-Host "Request sent to /llm/generate - check your LLM service terminal for the POST log"
