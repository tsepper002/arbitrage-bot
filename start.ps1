<#
.SYNOPSIS
    Arbitrage Bot — Quick Start (PowerShell)
.DESCRIPTION
    Pulls latest code, installs dependencies, and starts the bot.
    API keys are loaded from .env file (copy .env.example to .env).
.PARAMETER Mode
    Execution mode: 'dry-run' (default) or 'live'
.EXAMPLE
    .\start.ps1                # dry-run (default)
    .\start.ps1 -Mode live     # live trading
    .\start.ps1 dry-run        # explicit dry-run
#>
param(
    [ValidateSet("dry-run", "live")]
    [string]$Mode = "dry-run"
)

Set-Location $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Arbitrage Bot - Quick Start" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`n=== Stashing local changes and pulling latest code ===" -ForegroundColor Yellow
git stash 2>$null
git pull
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] git pull failed - running with local code" -ForegroundColor DarkYellow
}
git stash pop 2>$null

Write-Host "`n=== Installing / updating dependencies ===" -ForegroundColor Yellow
pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] pip install failed - some features may not work" -ForegroundColor DarkYellow
}

Write-Host "`n=== Starting bot in $Mode mode ===" -ForegroundColor Green
Write-Host ""
python main.py --mode $Mode
