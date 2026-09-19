$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
& "$ScriptDir\.venv\Scripts\python.exe" "$ScriptDir\agent.py" @args
