@echo off
chcp 65001 >nul
echo ========================================
echo   MIYA - Web Terminal System
echo ========================================
echo.
echo [Starting] Miya Web Terminal System...
echo.

REM Check virtual environment
if not exist venv (
    echo [ERROR] Virtual environment not found
    echo Please run install.bat first
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install requirements
echo [Info] Installing web dependencies...
pip install fastapi uvicorn aiohttp -q
if errorlevel 1 (
    echo [Error] Failed to install web dependencies
    pause
    exit /b 1
)

REM Start web server
echo [Info] Starting web server on http://localhost:8080
echo.
python webnet/TerminalNet/server.py

pause
