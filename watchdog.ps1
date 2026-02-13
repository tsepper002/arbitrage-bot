# ============================================================================
# Arbitrage Bot Watchdog Script for Windows 11
# Monitors heartbeat file and restarts bot if it stops responding
# Part of A7: 3-level watchdog system
# ============================================================================

# Configuration
$HEARTBEAT_FILE = "heartbeat.txt"
$BOT_SCRIPT = "main.py"
$PYTHON_EXE = "python"  # Or full path: "C:\Python312\python.exe"
$MAX_HEARTBEAT_AGE_SEC = 120  # 2 minutes without heartbeat = restart
$CHECK_INTERVAL_SEC = 30  # Check every 30 seconds
$LOG_FILE = "watchdog.log"

# Function to write to log
function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "$timestamp [WATCHDOG] $Message"
    Write-Host $logMessage
    Add-Content -Path $LOG_FILE -Value $logMessage
}

# Function to check if bot process is running
function Get-BotProcess {
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -like "*arbitrage*" -or
        $_.CommandLine -like "*main.py*"
    }
}

# Function to kill bot process
function Stop-BotProcess {
    Write-Log "Attempting to stop bot process..."
    $processes = Get-BotProcess
    foreach ($proc in $processes) {
        Write-Log "Killing process PID $($proc.Id)"
        Stop-Process -Id $proc.Id -Force
    }
    Start-Sleep -Seconds 2
}

# Function to start bot
function Start-Bot {
    Write-Log "Starting arbitrage bot..."
    
    # Kill any existing instances first
    Stop-BotProcess
    
    # Start new instance
    $processArgs = @{
        FilePath = $PYTHON_EXE
        ArgumentList = @("-u", $BOT_SCRIPT)  # -u for unbuffered output
        WorkingDirectory = $PSScriptRoot
        WindowStyle = "Minimized"
        PassThru = $true
    }
    
    try {
        $process = Start-Process @processArgs
        Write-Log "Bot started with PID $($process.Id)"
        return $true
    }
    catch {
        Write-Log "ERROR: Failed to start bot: $_"
        return $false
    }
}

# Function to check heartbeat
function Test-Heartbeat {
    if (-not (Test-Path $HEARTBEAT_FILE)) {
        Write-Log "WARNING: Heartbeat file not found: $HEARTBEAT_FILE"
        return $false
    }
    
    $fileInfo = Get-Item $HEARTBEAT_FILE
    $age = (Get-Date) - $fileInfo.LastWriteTime
    $ageSeconds = $age.TotalSeconds
    
    Write-Log "Heartbeat file age: $([int]$ageSeconds) seconds"
    
    if ($ageSeconds -gt $MAX_HEARTBEAT_AGE_SEC) {
        Write-Log "ERROR: Heartbeat too old ($([int]$ageSeconds)s > $MAX_HEARTBEAT_AGE_SEC s)"
        return $false
    }
    
    return $true
}

# Main watchdog loop
Write-Log "========================================="
Write-Log "Arbitrage Bot Watchdog Started"
Write-Log "Heartbeat file: $HEARTBEAT_FILE"
Write-Log "Max heartbeat age: $MAX_HEARTBEAT_AGE_SEC seconds"
Write-Log "Check interval: $CHECK_INTERVAL_SEC seconds"
Write-Log "========================================="

# Initial start
Start-Bot
Start-Sleep -Seconds 10  # Give it time to create heartbeat

while ($true) {
    Start-Sleep -Seconds $CHECK_INTERVAL_SEC
    
    $heartbeatOk = Test-Heartbeat
    
    if (-not $heartbeatOk) {
        Write-Log "🔴 HEARTBEAT FAILURE - Restarting bot..."
        Start-Bot
        Start-Sleep -Seconds 10
    }
    else {
        Write-Log "✅ Heartbeat OK"
    }
}

# ============================================================================
# INSTALLATION INSTRUCTIONS for Windows 11
# ============================================================================
# 1. Save this file as: watchdog.ps1
# 
# 2. Open PowerShell as Administrator and run:
#    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#
# 3. Test the script manually:
#    cd path\to\arbitrage-bot
#    .\watchdog.ps1
#
# 4. Setup Windows Task Scheduler for auto-start:
#    a. Open Task Scheduler (taskschd.msc)
#    b. Create New Task (not Basic Task)
#    c. General tab:
#       - Name: "Arbitrage Bot Watchdog"
#       - Run whether user is logged on or not: CHECK
#       - Run with highest privileges: CHECK
#    d. Triggers tab:
#       - New -> Begin the task: At startup
#       - Delay task for: 1 minute
#    e. Actions tab:
#       - New -> Action: Start a program
#       - Program: powershell.exe
#       - Arguments: -ExecutionPolicy Bypass -File "C:\path\to\arbitrage-bot\watchdog.ps1"
#       - Start in: C:\path\to\arbitrage-bot
#    f. Conditions tab:
#       - UNCHECK "Start the task only if the computer is on AC power"
#    g. Settings tab:
#       - If the task fails, restart every: 1 minute
#       - Attempt to restart up to: 3 times
#       - If the running task does not end when requested, force it to stop: CHECK
#
# 5. Test Task Scheduler setup:
#    - Right-click task -> Run
#    - Check watchdog.log file for output
#
# 6. Reboot and verify:
#    - After reboot, check if bot is running
#    - Check watchdog.log for activity
# ============================================================================
