@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"

set "MIYA_BUILD_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "MIYA_BUILD_PYTHON=.venv\Scripts\python.exe"

echo.
echo ================================================================
echo   MIYA Build System
echo ================================================================
echo.
echo   Use the interactive menu to build DSH and/or the Desktop app.
echo   DSH Web runtime must be built before Electron (option [1] or [3]).
echo.

if "%~1"=="" (
    %MIYA_BUILD_PYTHON% scripts\build.py menu
) else (
    %MIYA_BUILD_PYTHON% scripts\build.py %*
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo ================================================================
    echo   [ERROR] Build failed with exit code %ERRORLEVEL%
    echo ================================================================
    echo.
    pause
) else (
    echo.
    echo ================================================================
    echo   [OK] Build completed successfully
    echo ================================================================
    echo.
    pause
)
exit /b %ERRORLEVEL%
