$body = @{
    instruction = "Open Chrome browser"
    execute = $false
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:8000/llm/steps `
    -Method POST `
    -ContentType "application/json" `
    -Body $body `
    -UseBasicParsing
