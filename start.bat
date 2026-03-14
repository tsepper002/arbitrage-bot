@echo off
REM ============================================================
REM  Arbitrage Bot — Quick Start (Windows)
REM  Usage:
REM    start.bat                  — pull latest code & run dry-run
REM    start.bat live             — pull latest code & run live
REM    start.bat dry-run          — pull latest code & run dry-run
REM
REM  First time? Run update.bat first to switch to the right branch.
REM  API keys go in .env file (not in settings.py!)
REM  Copy .env.example to .env and fill in your keys.
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo  Arbitrage Bot — Quick Start
echo ============================================================

echo.
echo === Pulling latest code ===
REM Abort any stuck merge conflicts first
git merge --abort 2>nul
git stash 2>nul
git pull
if errorlevel 1 (
    echo [WARNING] git pull failed — running with local code
)
git stash pop 2>nul

echo.
echo === Installing / updating dependencies ===
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [WARNING] pip install failed — some features may not work
)

REM Create .env if it doesn't exist
if not exist .env (
    if exist .env.example (
        copy /Y .env.example .env >nul
        echo [INFO] Created .env from template — edit it with your API keys!
    )
)

set MODE=dry-run
if /I "%~1"=="live" set MODE=live
if /I "%~1"=="dry-run" set MODE=dry-run

echo.
echo === Starting bot in %MODE% mode ===
echo.
python main.py --mode %MODE%
