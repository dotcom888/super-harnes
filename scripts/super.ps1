$ScriptDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (Test-Path $PythonExe) {
    & $PythonExe (Join-Path $ScriptDir "main.py") @args
} else {
    & python (Join-Path $ScriptDir "main.py") @args
}
