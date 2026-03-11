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

REM Set Python to use virtual environment
set PYTHON_EXE=%~dp0venv\Scripts\python.exe

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
echo 3. Start Web UI (Frontend + Backend)
echo 4. Start Desktop UI (Electron)
echo 5. Start Runtime API Server
echo 6. Start Health Check
echo 7. Check System Status
echo 8. Exit
echo.
set /p choice=Select mode (1-8):

if "%choice%"=="1" goto main
if "%choice%"=="2" goto qq
if "%choice%"=="3" goto web
if "%choice%"=="4" goto desktop
if "%choice%"=="5" goto api
if "%choice%"=="6" goto health
if "%choice%"=="7" goto status
if "%choice%"=="8" goto end

echo [ERROR] Invalid choice
pause
goto menu

:main
echo.
echo [Starting] Main Program (Full Mode)...
echo.
echo [Info] Testing imports first...
"%PYTHON_EXE%" test_imports.py
if %errorlevel% neq 0 (
    echo [ERROR] Import test failed
    pause
    goto menu
)
echo.
echo [Info] Launching main program...
"%PYTHON_EXE%" run/main.py
goto end

:qq
echo.
echo [Starting] QQ Bot...
echo.
"%PYTHON_EXE%" run/qq_main.py
goto end

:web
echo.
echo [Starting] Web UI (Frontend + Backend)...
echo.
"%PYTHON_EXE%" run/web_main.py
goto end

:desktop
echo.
echo [Starting] Desktop UI (Electron)...
echo.
echo [Info] Starting Miya Desktop...
echo.
"%PYTHON_EXE%" run/desktop_main.py
goto end

:api
echo.
echo [Starting] Runtime API Server...
echo.
"%PYTHON_EXE%" run/runtime_api_start.py
goto end

:health
echo.
echo [Starting] Health Check...
echo.
"%PYTHON_EXE%" run/health.py
goto end

:status
echo.
echo [Status] System Status Check...
echo.
"%PYTHON_EXE%" -c "import sys; print('Python Version:', sys.version.split()[0]); import platform; print('OS:', platform.system(), platform.version()); print('Machine:', platform.machine()); print('Processor:', platform.processor())"
echo.
pause
goto menu

:end
echo.
echo [Done] Program exited
pause
