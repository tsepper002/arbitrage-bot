@echo off
REM ============================================================
REM  Arbitrage Bot — One-Time Branch Update (Windows)
REM
REM  Run this ONCE to switch from the old branch to the new
REM  working branch with all fixes:
REM    - Bybit apiTimestamp fix
REM    - All 14 strategies implemented
REM    - Live trading + dry-run modes
REM    - Telegram notifications
REM    - .env file for API keys
REM
REM  After running this, use start.bat to launch the bot.
REM ============================================================

cd /d "%~dp0"

echo ============================================================
echo  Arbitrage Bot — Branch Update
echo ============================================================

REM Step 1: Abort any stuck merge
echo.
echo [1/6] Cleaning up any stuck merge conflicts...
git merge --abort 2>nul
git checkout -- . 2>nul

REM Step 2: Save any local changes
echo [2/6] Saving your local changes (API keys, etc.)...
if exist .env (
    copy /Y .env .env.backup >nul
    echo       Backed up .env to .env.backup
)
git stash 2>nul

REM Step 3: Fetch latest code
echo [3/6] Fetching latest code from GitHub...
git fetch origin

REM Step 4: Switch to the working branch
echo [4/6] Switching to working branch...
git checkout copilot/fix-bot-start-issues-again 2>nul
if errorlevel 1 (
    echo       Creating local tracking branch...
    git checkout -b copilot/fix-bot-start-issues-again origin/copilot/fix-bot-start-issues-again
)
git pull origin copilot/fix-bot-start-issues-again

REM Step 5: Install dependencies
echo [5/6] Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [WARNING] pip install had issues - trying again...
    pip install -r requirements.txt
)

REM Step 6: Set up .env file
echo [6/6] Setting up configuration...
if exist .env.backup (
    copy /Y .env.backup .env >nul
    echo       Restored your .env from backup
) else if not exist .env (
    copy /Y .env.example .env >nul
    echo       Created .env from template
    echo.
    echo ============================================================
    echo  IMPORTANT: Edit .env with your API keys!
    echo  Open .env in notepad:  notepad .env
    echo ============================================================
)

echo.
echo ============================================================
echo  UPDATE COMPLETE!
echo.
echo  To start the bot:
echo    py main.py --mode dry-run
echo.
echo  Or use start.bat:
echo    start.bat              (dry-run mode)
echo    start.bat live         (live trading)
echo ============================================================
pause
