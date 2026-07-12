# Start Frontend Server
# Run this script to start the Vite frontend server

Write-Host "🚀 Starting Agentception Frontend Server..." -ForegroundColor Cyan

# Make sure we're in the project root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Change to ui directory
Set-Location ui

# Check if node_modules exists
if (-not (Test-Path "node_modules")) {
    Write-Host "📦 Installing dependencies (first time only)..." -ForegroundColor Yellow
    npm install
}

# Start Vite dev server
Write-Host "🔧 Starting Vite dev server on http://localhost:8080..." -ForegroundColor Yellow
npm run dev

