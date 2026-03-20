@echo off
setlocal
cd /d %~dp0
echo [1/2] Syncing dependencies with uv...
uv sync --quiet
echo [2/2] Launching ActivityWatch in background...
start /b .venv\Scripts\pythonw.exe -m aw_pywebview
echo Done! ActivityWatch is now running silently.
