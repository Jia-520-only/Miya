@echo off
chcp 65001 >nul
echo ========================================
echo   MIYA - Launch Menu
echo ========================================
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

REM Check configuration file
if not exist config\.env (
    echo [ERROR] Configuration file not found: config\.env
    echo Please create and configure config\.env file
    pause
    exit /b 1
)

REM Display menu
:menu
cls
echo ========================================
echo   MIYA - Launch Menu
echo ========================================
echo.
echo 1. Start Main Program (Full Mode)
echo 2. Start QQ Bot
echo 3. Start PC UI
echo 4. Start Runtime API Server
echo 5. Start Health Check
echo 6. Check System Status
echo 7. Exit
echo.
set /p choice=Select mode (1-7):

if "%choice%"=="1" goto main
if "%choice%"=="2" goto qq
if "%choice%"=="3" goto pc
if "%choice%"=="4" goto api
if "%choice%"=="5" goto health
if "%choice%"=="6" goto status
if "%choice%"=="7" goto end

echo [ERROR] Invalid choice
pause
goto menu

:main
echo.
echo [Starting] Main Program (Full Mode)...
echo.
echo [Info] Testing imports first...
python test_imports.py
if %errorlevel% neq 0 (
    echo [ERROR] Import test failed
    pause
    goto menu
)
echo.
echo [Info] Launching main program...
python run/main.py
goto end

:qq
echo.
echo [Starting] QQ Bot...
echo.
python run/qq_main.py
goto end

:pc
echo.
echo [Starting] PC UI...
echo.
python pc_ui/main.py
goto end

:api
echo.
echo [Starting] Runtime API Server...
echo.
python -c "from core.runtime_api_server import RuntimeAPIServer; import asyncio; server = RuntimeAPIServer(); asyncio.run(server.start())"
goto end

:health
echo.
echo [Starting] Health Check...
echo.
python run/health.py
goto end

:status
echo.
echo [Status] System Status Check...
echo.
python -c "import sys; print('Python Version:', sys.version.split()[0]); import platform; print('OS:', platform.system(), platform.version()); print('Machine:', platform.machine()); print('Processor:', platform.processor())"
echo.
pause
goto menu

:end
echo.
echo [Done] Program exited
pause
