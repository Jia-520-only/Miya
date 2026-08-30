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
echo 8. Custom Combo - Select components
echo 9. Background Mode
echo 0. Exit
echo.
set /p choice=Select mode (0-9):

REM Check for multi-select
echo %choice% | findstr /C:" " >nul
if %errorlevel%==0 goto custom_multi
echo %choice% | findstr /C:"," >nul
if %errorlevel%==0 goto custom_multi

REM Single select
if "%choice%"=="1" goto main
if "%choice%"=="2" goto qq
if "%choice%"=="3" goto web
if "%choice%"=="4" goto desktop
if "%choice%"=="5" goto api
if "%choice%"=="6" goto health
if "%choice%"=="7" goto status
if "%choice%"=="8" goto custom
if "%choice%"=="9" goto background
if "%choice%"=="0" goto end

echo [ERROR] Invalid choice
pause
goto menu

:custom_multi
REM Multi-select mode
goto custom

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

:custom
cls
echo ========================================
echo   Custom Combo - Select Components
echo ========================================
echo.
echo Select components to start (enter numbers separated by space):
echo.
echo 1. Main Program (Backend API)
echo 2. QQ Bot
echo 3. Web UI
echo 4. Desktop UI
echo 0. Back to menu
echo.
set /p components=Select components:

if "%components%"=="0" goto menu

echo.
echo [Starting] Custom combo: %components%
echo.

REM Start components in new windows
for %%a in (%components%) do (
    if "%%a"=="1" start "Miya-Main" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/main.py"
    if "%%a"=="2" start "Miya-QQ" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/qq_main.py"
    if "%%a"=="3" start "Miya-Web" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/web_main.py"
    if "%%a"=="4" start "Miya-Desktop" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/desktop_main.py"
)

echo.
echo [OK] Components started in new windows
echo Press any key to return to menu...
pause >nul
goto menu

:background
cls
echo ========================================
echo   Background Mode
echo ========================================
echo.
echo 1. Main + QQ Bot
echo 2. Main + Desktop UI
echo 3. Main + QQ + Desktop
echo 4. Main + Web + Desktop
echo 0. Back to menu
echo.
set /p bg_choice=Select (0-4):

if "%bg_choice%"=="0" goto menu
if "%bg_choice%"=="1" goto bg1
if "%bg_choice%"=="2" goto bg2
if "%bg_choice%"=="3" goto bg3
if "%bg_choice%"=="4" goto bg4
goto menu

:bg1
start "Miya-Main" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/main.py"
timeout /t 2 /nobreak >nul
start "Miya-QQ" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/qq_main.py"
echo [OK] Started Main + QQ
pause
goto menu

:bg2
start "Miya-Main" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/main.py"
timeout /t 2 /nobreak >nul
start "Miya-Desktop" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/desktop_main.py"
echo [OK] Started Main + Desktop
pause
goto menu

:bg3
start "Miya-Main" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/main.py"
timeout /t 2 /nobreak >nul
start "Miya-QQ" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/qq_main.py"
timeout /t 1 /nobreak >nul
start "Miya-Desktop" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/desktop_main.py"
echo [OK] Started Main + QQ + Desktop
pause
goto menu

:bg4
start "Miya-Main" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/main.py"
timeout /t 2 /nobreak >nul
start "Miya-Web" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/web_main.py"
timeout /t 1 /nobreak >nul
start "Miya-Desktop" cmd /k "cd /d %~dp0 && "%PYTHON_EXE%" run/desktop_main.py"
echo [OK] Started Main + Web + Desktop
pause
goto menu

:end
echo.
echo [Done] Program exited
pause
