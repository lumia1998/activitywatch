@echo off
setlocal
cd /d %~dp0
set BASE_DIR=%~dp0

:: Ensure source modules win over site-packages
set PYTHONPATH=%BASE_DIR%aw-core;%BASE_DIR%aw-client;%BASE_DIR%aw-server;%BASE_DIR%aw-watcher-afk;%BASE_DIR%aw-watcher-window;%BASE_DIR%aw-watcher-input;%BASE_DIR%aw-pywebview;%PYTHONPATH%

:: Check if .venv exists
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] No virtual environment found, creating with uv...
    uv venv .venv
    echo [2/3] Syncing dependencies with uv...
    uv sync
    echo [3/3] Launching ActivityWatch from source...
) else (
    echo [1/2] Virtual environment found, syncing dependencies with uv...
    uv sync
    echo [2/2] Launching ActivityWatch from source...
)

.venv\Scripts\python.exe -m aw_pywebview
pause
