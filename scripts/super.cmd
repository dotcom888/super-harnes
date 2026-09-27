@echo off
setlocal
set "PROJECT_ROOT=%~dp0..\"
"%PROJECT_ROOT%.venv\Scripts\python.exe" "%PROJECT_ROOT%main.py" %*
endlocal
