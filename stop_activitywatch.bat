@echo off
echo Stopping ActivityWatch processes...
taskkill /f /im pythonw.exe /t 2>nul
taskkill /f /im python.exe /t 2>nul
echo Done.
pause
