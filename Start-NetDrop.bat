@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo NetDrop is not set up yet.
  echo Run the installation steps in README.md once, then open this file again.
  pause
  exit /b 1
)

start "NetDrop server" /b ".venv\Scripts\python.exe" -m app.main
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8000
echo NetDrop is running. Keep this window open while people share files.
pause
