@echo off
setlocal
cd /d %~dp0
echo [1/1] Launching ActivityWatch...
:: Ensure absolute paths for submodules in PYTHONPATH
set BASE_DIR=%~dp0
set PYTHONPATH=%BASE_DIR%aw-core;%BASE_DIR%aw-client;%BASE_DIR%aw-server;%BASE_DIR%aw-watcher-afk;%BASE_DIR%aw-watcher-window;%BASE_DIR%aw-pywebview;%PYTHONPATH%
.venv\Scripts\python.exe -m aw_pywebview
pause
