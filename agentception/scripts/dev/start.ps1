# Unified Start Script for Agentception
# Starts both backend and frontend servers in parallel

Write-Host "🚀 Starting Agentception (Backend + Frontend)..." -ForegroundColor Cyan
Write-Host ""

# Make sure we're in the project root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Check for virtual environment
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "❌ Virtual environment not found. Please run: python -m venv .venv" -ForegroundColor Red
    Write-Host "   Then install locked dependencies: uv sync --frozen --group dev" -ForegroundColor Yellow
    exit 1
}

# Check for node_modules in ui directory
if (-not (Test-Path "ui\node_modules")) {
    Write-Host "📦 Installing frontend dependencies (first time only)..." -ForegroundColor Yellow
    Set-Location ui
    npm install
    Set-Location ..
    Write-Host ""
}

# Function to start backend
function Start-Backend {
    Write-Host "🔧 Starting Backend Server on http://localhost:8000..." -ForegroundColor Yellow
    
    # Activate virtual environment
    & .\.venv\Scripts\Activate.ps1
    
    # Start uvicorn
    python -m uvicorn server.app:app --reload --port 8000 --host 127.0.0.1
}

# Function to start frontend
function Start-Frontend {
    Write-Host "🔧 Starting Frontend Server on http://localhost:8080..." -ForegroundColor Yellow
    
    Set-Location ui
    npm run dev
    Set-Location ..
}

# Start both servers in separate PowerShell windows
Write-Host "📝 Opening Backend in new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath'; & .\.venv\Scripts\Activate.ps1; Write-Host '🔧 Backend Server (http://localhost:8000)' -ForegroundColor Yellow; python -m uvicorn server.app:app --reload --port 8000 --host 127.0.0.1"

Write-Host "📝 Opening Frontend in new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath\ui'; Write-Host '🔧 Frontend Server (http://localhost:8080)' -ForegroundColor Yellow; npm run dev"

Write-Host ""
Write-Host "✅ Both servers are starting in separate windows!" -ForegroundColor Green
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor Gray
Write-Host "   Frontend: http://localhost:8080" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to exit this script (servers will continue running)..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
