@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo NetDrop is not set up yet.
  echo Run the installation steps in README.md once, then open this file again.
  pause
  exit /b 1
)

where cloudflared >nul 2>nul
if errorlevel 1 (
  echo cloudflared is not installed.
  echo Install it with: winget install --id Cloudflare.cloudflared
  pause
  exit /b 1
)

if "%~1"=="" (
  set "NETDROP_TUNNEL=netdrop"
) else (
  set "NETDROP_TUNNEL=%~1"
)

start "NetDrop server" /b ".venv\Scripts\python.exe" -m app.main
timeout /t 2 /nobreak >nul
start "NetDrop Cloudflare Tunnel" /b cloudflared tunnel run "%NETDROP_TUNNEL%"
start "" http://127.0.0.1:8000
echo NetDrop and the Cloudflare Tunnel are starting.
echo Keep this window open while people share files.
pause
