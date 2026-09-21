@echo off
setlocal
set "PROJECT_ROOT=%~dp0..\"
cd /d "%PROJECT_ROOT%"
"%PROJECT_ROOT%.venv\Scripts\python.exe" "%PROJECT_ROOT%main.py" %*
endlocal
