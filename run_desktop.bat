@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   Starting Super-Harnes Agent Desktop (Electron)
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=%SCRIPT_DIR%.venv\Scripts\python.exe"
)

echo [1/2] Starting Super-Harnes Backend (http://127.0.0.1:8765)...
start "Super-Harnes Backend" /min "%PYTHON_CMD%" "%SCRIPT_DIR%server\run_server.py" 8765

timeout /t 2 /nobreak >nul

echo [2/2] Launching Electron Desktop Window...
cd /d "%SCRIPT_DIR%desktop"
call npm run electron

pause
