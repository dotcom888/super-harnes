$ScriptDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
& "$ScriptDir\.venv\Scripts\python.exe" "$ScriptDir\main.py" @args
