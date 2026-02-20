@echo off
REM ============================================================
REM  Arbitrage Bot — Quick Start (Windows)
REM  Usage:
REM    start.bat                  — pull latest code & run dry-run
REM    start.bat live             — pull latest code & run live
REM    start.bat dry-run          — pull latest code & run dry-run
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo  Arbitrage Bot — Quick Start
echo ============================================================

echo.
echo === Pulling latest changes ===
git pull
if errorlevel 1 (
    echo [WARNING] git pull failed — running with local code
)

echo.
echo === Installing / updating dependencies ===
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [WARNING] pip install failed — some features may not work
)

set MODE=dry-run
if /I "%~1"=="live" set MODE=live
if /I "%~1"=="dry-run" set MODE=dry-run

echo.
echo === Starting bot in %MODE% mode ===
echo.
python main.py --mode %MODE%
