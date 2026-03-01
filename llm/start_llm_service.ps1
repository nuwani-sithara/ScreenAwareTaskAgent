# Start LLM API Service
# Port: 8002

Write-Host "🚀 Starting LLM API Service..." -ForegroundColor Cyan

# Activate virtual environment if exists
$venvPath = "..\venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "📦 Activating virtual environment..." -ForegroundColor Yellow
    & $venvPath
}

# Check if Ollama is running
Write-Host "🔍 Checking Ollama availability..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -Method GET -TimeoutSec 2
    Write-Host "✅ Ollama is running" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Ollama is not running. Please start Ollama first." -ForegroundColor Red
    Write-Host "   Run: ollama serve" -ForegroundColor Yellow
}

# Start the service
Write-Host "🚀 Starting LLM API Service on port 8002..." -ForegroundColor Cyan
Write-Host ""
Write-Host "Endpoints available:" -ForegroundColor Green
Write-Host "  • POST http://localhost:8002/llm/generate" -ForegroundColor White
Write-Host "  • POST http://localhost:8002/llm/simple" -ForegroundColor White
Write-Host "  • GET  http://localhost:8002/llm/health" -ForegroundColor White
Write-Host "  • GET  http://localhost:8002/llm/status" -ForegroundColor White
Write-Host ""

# Run the service
python -m uvicorn llm.api:app --reload --port 8002 --host 0.0.0.0
