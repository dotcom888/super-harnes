@echo off
setlocal
set "PROJECT_ROOT=%~dp0..\"
if exist "%PROJECT_ROOT%.venv\Scripts\python.exe" (
    "%PROJECT_ROOT%.venv\Scripts\python.exe" "%PROJECT_ROOT%main.py" %*
) else (
    python "%PROJECT_ROOT%main.py" %*
)
endlocal
