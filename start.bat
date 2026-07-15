@echo off
title Codespace Agent
cd /d "%~dp0"
echo Starting Codespace Agent...
echo.
set PORT=8000
set PROXY_PORT=8787
set SOCKS_HOST=
set SOCKS_PORT=12334
start "CORS Proxy" /B python proxy.py --port 8787 --socks-host  --socks-port 12334
start "CodeAgent" /B python server.py --port 8000
timeout /t 2 /nobreak >nul
start http://localhost:8000/%HTML_FILE%
echo.
echo Servers running. Close this window to stop.
pause >nul
