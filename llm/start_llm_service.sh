#!/bin/bash
# Start LLM API Service
# Port: 8002

echo "🚀 Starting LLM API Service..."

# Activate virtual environment if exists
if [ -f "../venv/bin/activate" ]; then
    echo "📦 Activating virtual environment..."
    source ../venv/bin/activate
fi

# Check if Ollama is running
echo "🔍 Checking Ollama availability..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama is running"
else
    echo "⚠️  Ollama is not running. Please start Ollama first."
    echo "   Run: ollama serve"
fi

# Start the service
echo "🚀 Starting LLM API Service on port 8002..."
echo ""
echo "Endpoints available:"
echo "  • POST http://localhost:8002/llm/generate"
echo "  • POST http://localhost:8002/llm/simple"
echo "  • GET  http://localhost:8002/llm/health"
echo "  • GET  http://localhost:8002/llm/status"
echo ""

# Run the service
python -m uvicorn llm.api:app --reload --port 8002 --host 0.0.0.0
