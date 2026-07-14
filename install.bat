@echo off
title Codespace Agent Installer
cd /d "%~dp0"

:: ================================================================
::  Simplified Installer - No complex blocks
:: ================================================================

set "HTTP_PORT=8000"
set "PROXY_PORT=8787"
set "INSTALL_DIR=%USERPROFILE%\codespace-agent"
set "HTML_FILE=codespace-agent.html"
set "PYTHON_CMD=python"

echo.
echo ======================================================
echo   Codespace Agent - Installer (Simple)
echo   AI-Powered Coding Workspace
echo ======================================================
echo.

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Python not found! Please install Python 3.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo [OK] Python %PY_VER% found
echo.

:: Choose mode
echo 1) Quick Start (Python server + Python proxy)
echo 2) Files Only (just copy files)
echo.
set /p "MODE=Choose [1 or 2]: "
if "%MODE%"=="1" goto mode_full
if "%MODE%"=="2" goto mode_filesonly
echo Invalid choice.
pause
exit /b 1

:mode_full
set "START_MODE=full"
goto continue

:mode_filesonly
set "START_MODE=filesonly"
goto continue

:continue

:: Optional SOCKS5
set "USE_SOCKS=0"
if "%START_MODE%"=="full" (
    echo.
    set /p "USE_SOCKS_CHOICE=Use SOCKS5 proxy? (for VPN) [y/N]: "
    if /i "%USE_SOCKS_CHOICE%"=="y" (
        set "USE_SOCKS=1"
        set /p "SOCKS_ADDR=SOCKS5 address (e.g., 127.0.0.1:1080): "
        if "%SOCKS_ADDR%"=="" set "SOCKS_ADDR=127.0.0.1:1080"
    )
)

:: Ports
if "%START_MODE%"=="full" (
    echo.
    set /p "CUSTOM_HTTP=HTTP port [%HTTP_PORT%]: "
    if not "%CUSTOM_HTTP%"=="" set "HTTP_PORT=%CUSTOM_HTTP%"
    set /p "CUSTOM_PROXY=CORS proxy port [%PROXY_PORT%]: "
    if not "%CUSTOM_PROXY%"=="" set "PROXY_PORT=%CUSTOM_PROXY%"
)

:: Installation directory
echo.
echo Default install dir: %INSTALL_DIR%
set /p "CUSTOM_DIR=Press Enter for default, or type custom path: "
if not "%CUSTOM_DIR%"=="" set "INSTALL_DIR=%CUSTOM_DIR%"
echo Installing to: %INSTALL_DIR%
echo.

:: Confirm
echo Summary:
echo   Mode: %START_MODE%
if "%START_MODE%"=="full" (
    echo   HTTP Port: %HTTP_PORT%
    echo   Proxy Port: %PROXY_PORT%
    if %USE_SOCKS%==1 echo   SOCKS5: %SOCKS_ADDR%
)
echo.
set /p "CONFIRM=Proceed? [Y/n]: "
if /i "%CONFIRM%"=="n" (
    echo Cancelled.
    pause
    exit /b 0
)

:: Create installation directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Copy files
echo.
echo --- Copying files ---
if exist "%CD%\index.html" (
    copy /y "%CD%\index.html" "%INSTALL_DIR%\%HTML_FILE%" >nul
    echo [OK] Copied index.html as %HTML_FILE%
) else (
    echo [ERR] index.html not found in current folder!
    pause
    exit /b 1
)

if exist "%CD%\proxy.py" (
    copy /y "%CD%\proxy.py" "%INSTALL_DIR%\proxy.py" >nul
    echo [OK] Copied proxy.py
) else (
    echo [WARN] proxy.py not found - proxy will not be available.
)

if exist "%CD%\proxy.js" (
    copy /y "%CD%\proxy.js" "%INSTALL_DIR%\proxy.js" >nul
    echo [OK] Copied proxy.js
) else (
    echo [WARN] proxy.js not found - proxy will not be available.
)

:: Create start.bat
echo.
echo Creating start.bat...
(
echo @echo off
echo title Codespace Agent
echo cd /d "%%~dp0"
echo echo Starting Codespace Agent...
echo echo.
echo start "CORS Proxy" /B python proxy.py --port %PROXY_PORT%
echo start "HTTP Server" /B python -m http.server %HTTP_PORT%
echo timeout /t 2 /nobreak ^>nul
echo start http://localhost:%HTTP_PORT%/%HTML_FILE%
echo echo.
echo echo Servers running. Close this window to stop.
echo pause ^>nul
) > "%INSTALL_DIR%\start.bat"
echo [OK] Created start.bat

:: Create stop.bat
(
echo @echo off
echo echo Stopping...
echo taskkill /fi "WindowTitle eq CORS Proxy*" /f >nul 2>&1
echo taskkill /fi "WindowTitle eq HTTP Server*" /f >nul 2>&1
echo taskkill /fi "WindowTitle eq Codespace Agent*" /f >nul 2>&1
echo echo Done.
echo pause
) > "%INSTALL_DIR%\stop.bat"
echo [OK] Created stop.bat

:: Create README
(
echo # Codespace Agent
echo.
echo Quick Start:
echo   run start.bat
echo.
echo App: http://localhost:%HTTP_PORT%/%HTML_FILE%
echo Proxy: http://127.0.0.1:%PROXY_PORT%
) > "%INSTALL_DIR%\README.md"
echo [OK] Created README.md

:: Install pysocks if SOCKS5 enabled
if %USE_SOCKS%==1 (
    echo.
    echo Installing pysocks for SOCKS5 support...
    "%PYTHON_CMD%" -m pip install pysocks --quiet 2>nul
    if %errorlevel%==0 ( echo [OK] pysocks installed ) else ( echo [WARN] pysocks install failed )
)

:: Start services (if full mode)
if "%START_MODE%"=="filesonly" goto filesonly_done

echo.
echo --- Starting services ---
cd /d "%INSTALL_DIR%"

:: Start proxy (if proxy.py exists)
if exist "%INSTALL_DIR%\proxy.py" (
    echo Starting CORS proxy on port %PROXY_PORT%...
    start "CORS Proxy" /B python proxy.py --port %PROXY_PORT%
    timeout /t 2 /nobreak >nul
    echo [OK] Proxy started
) else (
    echo [WARN] proxy.py missing - skipping proxy
)

:: Start HTTP server
echo Starting HTTP server on port %HTTP_PORT%...
start "HTTP Server" /B python -m http.server %HTTP_PORT%
timeout /t 2 /nobreak >nul
echo [OK] Server started

:: Open browser
echo.
echo Opening app in browser...
start http://localhost:%HTTP_PORT%/%HTML_FILE%

:filesonly_done
echo.
echo ======================================================
echo Installation complete!
echo.
if "%START_MODE%"=="full" (
    echo App URL: http://localhost:%HTTP_PORT%/%HTML_FILE%
    echo Proxy: http://127.0.0.1:%PROXY_PORT%
    echo.
    echo To stop services, run: %INSTALL_DIR%\stop.bat
) else (
    echo Files copied to: %INSTALL_DIR%
    echo To start, run: %INSTALL_DIR%\start.bat
)
echo.
echo Press any key to close this window.
pause >nul
exit /b 0