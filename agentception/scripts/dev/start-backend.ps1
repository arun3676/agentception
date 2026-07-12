# Start Backend Server
# Run this script to start the FastAPI backend server

Write-Host "🚀 Starting Agentception Backend Server..." -ForegroundColor Cyan

# Make sure we're in the project root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Activate virtual environment
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
    Write-Host "✅ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "❌ Virtual environment not found. Please run: python -m venv .venv" -ForegroundColor Red
    exit 1
}

# Start uvicorn from project root (not server directory)
# This allows relative imports in app.py to work correctly
Write-Host "🔧 Starting uvicorn server on http://localhost:8000..." -ForegroundColor Yellow
Write-Host "   (Running from project root to support relative imports)" -ForegroundColor Gray
python -m uvicorn server.app:app --reload --port 8000 --host 127.0.0.1

