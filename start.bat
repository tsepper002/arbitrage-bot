@echo off
REM ============================================================
REM  Arbitrage Bot — Quick Start (Windows)
REM  Usage:
REM    start.bat                  — pull latest code & run dry-run
REM    start.bat live             — pull latest code & run live
REM    start.bat dry-run          — pull latest code & run dry-run
REM ============================================================

cd /d "%~dp0"

echo === Pulling latest changes ===
git pull

echo === Installing / updating dependencies ===
pip install -r requirements.txt

set MODE=dry-run
if /I "%~1"=="live" set MODE=live
if /I "%~1"=="dry-run" set MODE=dry-run

echo === Starting bot in %MODE% mode ===
python main.py --mode %MODE%
