@echo off
setlocal
cd /d %~dp0
echo [1/2] Syncing dependencies with uv...
uv sync --quiet
echo [2/2] Generating latest report (Today So Far)...
.venv\Scripts\python.exe -m aw_pywebview.cli --mode today_so_far
pause
