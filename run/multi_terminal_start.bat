@echo off
chcp 65001 >nul
echo ========================================
echo   MIYA - Multi-Terminal Mode
echo ========================================
echo.
echo [Starting] Miya Multi-Terminal System...
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

REM Start multi-terminal system
echo [Info] Launching multi-terminal shell...
echo.
python run/multi_terminal_main.py

pause
