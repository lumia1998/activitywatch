@echo off
setlocal
cd /d %~dp0

:: Check if .venv exists
if not exist ".venv\Scripts\pythonw.exe" (
    echo [1/3] No virtual environment found, creating with uv...
    uv venv .venv
    echo [2/3] Syncing dependencies with uv...
    uv sync --quiet
    echo [3/3] Launching ActivityWatch in background...
    start /b .venv\Scripts\pythonw.exe -m aw_pywebview
    echo Done! ActivityWatch is now running silently.
) else (
    echo [1/2] Syncing dependencies with uv...
    uv sync --quiet
    echo [2/2] Launching ActivityWatch in background...
    start /b .venv\Scripts\pythonw.exe -m aw_pywebview
    echo Done! ActivityWatch is now running silently.
)
