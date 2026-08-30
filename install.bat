@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

set "MIYA_BOOTSTRAP_PYTHON="
if exist ".venv\Scripts\python.exe" (
    set "MIYA_BOOTSTRAP_PYTHON=.venv\Scripts\python.exe"
) else (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 set "MIYA_BOOTSTRAP_PYTHON=python"
)

if not defined MIYA_BOOTSTRAP_PYTHON (
    py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 set "MIYA_BOOTSTRAP_PYTHON=py -3.11"
)

if not defined MIYA_BOOTSTRAP_PYTHON (
    echo [ERROR] Python 3.11 or newer is required. Install it from https://www.python.org/downloads/windows/
    exit /b 1
)

%MIYA_BOOTSTRAP_PYTHON% setup\scripts\install.py %*
set "MIYA_INSTALL_EXIT=%ERRORLEVEL%"
if not "%MIYA_INSTALL_EXIT%"=="0" (
    echo.
    echo [ERROR] MIYA dependency installation failed with exit code %MIYA_INSTALL_EXIT%.
    echo         The error details are shown above. Fix the reported issue and run install.bat again.
    pause
)
exit /b %MIYA_INSTALL_EXIT%
