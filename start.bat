@echo off
chcp 65001 >nul
title MIYA v4.1.11

:: ============================================================
::  MIYA v4.1.11 - Launch Center
::  
::  start.bat           Show menu
::  start.bat 1|2|3     Direct launch
::  start.bat a         Launch all
:: ============================================================

:: CLI direct
if /i "%1"=="1" goto :terminal
if /i "%1"=="t" goto :terminal
if /i "%1"=="2" goto :daemon
if /i "%1"=="d" goto :daemon
if /i "%1"=="3" goto :desktop
if /i "%1"=="4" goto :web
if /i "%1"=="w" goto :web
if /i "%1"=="a" goto :all

:menu
cls
echo.
echo ================================================================================
echo                         MIYA v4.1.11  Launch Center
echo ================================================================================
echo.
echo   [1] Terminal    DSH TUI + DeepSeek V4
echo   [2] Daemon      Backend (core + platforms + API :9800)
echo   [3] Desktop     Electron desktop app
echo   [4] Web UI      DSH Web (browser)
echo.
echo   [A] All         Start everything
echo   [0] Exit
echo.
echo ================================================================================
echo.

set /p "choice=Enter choice: "

if "%choice%"=="0" goto :exit
if "%choice%"=="1" goto :terminal
if /i "%choice%"=="t" goto :terminal
if "%choice%"=="2" goto :daemon
if /i "%choice%"=="d" goto :daemon
if "%choice%"=="3" goto :desktop
if "%choice%"=="4" goto :web
if /i "%choice%"=="w" goto :web
if /i "%choice%"=="a" goto :all

echo [ERROR] Invalid choice
timeout /t 1 >nul
goto :menu

:: ============================================================
:: DSH Host 公共启动（后台，供 TUI / Web / 前端复用）
:: ============================================================
:ensure_host
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found
    pause
    goto :menu
)
if not exist "%~dp0deepseek-harness\apps\cli\lib\bin.js" (
    echo [ERROR] DeepSeek Harness not found
    echo Run: build.bat dsh
    pause
    goto :menu
)
:: 独立进程启动 host（与控制台解耦、日志落盘）+ HTTP 就绪等待（详见 scripts/start_dsh_host.ps1）
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_dsh_host.ps1"
exit /b 0

:: ============================================================
:terminal
cls
echo.
echo ================================================================================
echo   MIYA Terminal (DSH TUI)
echo ================================================================================
echo.

if not exist "%~dp0tools\dsh-tui\node_modules\dsh-tui\bin\tui.js" (
    echo [ERROR] dsh-tui not found
    echo Run: cd tools\dsh-tui ^&^& npm install dsh-tui
    pause
    goto :menu
)

call :ensure_host

echo Starting MIYA Terminal (dsh-tui) in Windows Terminal...
where wt >nul 2>&1
if errorlevel 1 (
    start "MIYA Terminal" cmd /k powershell -NoProfile -ExecutionPolicy Bypass -File %~dp0tools\dsh-tui\launch_tui.ps1
) else (
    start "MIYA Terminal" wt cmd /k powershell -NoProfile -ExecutionPolicy Bypass -File %~dp0tools\dsh-tui\launch_tui.ps1
)
timeout /t 2 >nul
echo.
echo [OK] Terminal launched
goto :restart

:: ============================================================
:web
cls
echo.
echo ================================================================================
echo   MIYA DSH Web UI
echo ================================================================================
echo.

call :ensure_host

echo Opening DSH Web UI in browser...
start "" http://127.0.0.1:3199
timeout /t 2 >nul
echo.
echo [OK] Web UI launched (http://127.0.0.1:3199)
goto :restart

:: ============================================================
:daemon
cls
echo.
echo ================================================================================
echo   MIYA Daemon
echo ================================================================================
echo.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found
    pause
    goto :menu
)

echo Starting MIYA Daemon (API on port 9800)...
echo Press Ctrl+C to stop.
echo.
"%~dp0.venv\Scripts\python.exe" run/daemon.py --api-port 9800
echo.
echo [OK] Daemon stopped
goto :restart

:: ============================================================
:desktop
cls
echo.
echo ================================================================================
echo   MIYA Desktop (Electron)
echo ================================================================================
echo.

if not exist "miya_frontend\package.json" (
    echo [ERROR] miya_frontend not found
    pause
    goto :menu
)

:: Check if dependencies are properly installed.  A previous pnpm run can leave
:: npm packages under node_modules\.ignored; checking only for the directory (or
:: Electron) then lets the launch continue until Vite fails with MODULE_NOT_FOUND.
if not exist "miya_frontend\node_modules\" goto :desktop_install
call :restore_ignored_frontend_deps
if not exist "miya_frontend\node_modules\vite\bin\vite.js" goto :desktop_install
if not exist "miya_frontend\node_modules\@vitejs\plugin-vue\package.json" goto :desktop_install
if not exist "miya_frontend\node_modules\vue\package.json" goto :desktop_install
if not exist "miya_frontend\node_modules\unocss\package.json" goto :desktop_install
if not exist "miya_frontend\node_modules\vite-plugin-electron\package.json" goto :desktop_install
if not exist "miya_frontend\node_modules\electron\package.json" goto :desktop_install
if not exist "miya_frontend\node_modules\esbuild\package.json" goto :desktop_install
if not exist "miya_frontend\node_modules\electron\dist\electron.exe" goto :desktop_rebuild
goto :desktop_launch

:restore_ignored_frontend_deps
:: pnpm moves packages installed by another manager into .ignored. Restore the
:: small set required by the desktop dev server before falling back to npm.
if not exist "miya_frontend\node_modules\vite\bin\vite.js" if exist "miya_frontend\node_modules\.ignored\vite\bin\vite.js" move /Y "miya_frontend\node_modules\.ignored\vite" "miya_frontend\node_modules\vite" >nul
if not exist "miya_frontend\node_modules\vue\package.json" if exist "miya_frontend\node_modules\.ignored\vue\package.json" move /Y "miya_frontend\node_modules\.ignored\vue" "miya_frontend\node_modules\vue" >nul
if not exist "miya_frontend\node_modules\unocss\package.json" if exist "miya_frontend\node_modules\.ignored\unocss\package.json" move /Y "miya_frontend\node_modules\.ignored\unocss" "miya_frontend\node_modules\unocss" >nul
if not exist "miya_frontend\node_modules\vite-plugin-electron\package.json" if exist "miya_frontend\node_modules\.ignored\vite-plugin-electron\package.json" move /Y "miya_frontend\node_modules\.ignored\vite-plugin-electron" "miya_frontend\node_modules\vite-plugin-electron" >nul
if not exist "miya_frontend\node_modules\electron\package.json" if exist "miya_frontend\node_modules\.ignored\electron\package.json" move /Y "miya_frontend\node_modules\.ignored\electron" "miya_frontend\node_modules\electron" >nul
if not exist "miya_frontend\node_modules\esbuild\package.json" if exist "miya_frontend\node_modules\.ignored\esbuild\package.json" move /Y "miya_frontend\node_modules\.ignored\esbuild" "miya_frontend\node_modules\esbuild" >nul
if not exist "miya_frontend\node_modules\@vitejs" mkdir "miya_frontend\node_modules\@vitejs" >nul 2>&1
if not exist "miya_frontend\node_modules\@vitejs\plugin-vue\package.json" if exist "miya_frontend\node_modules\.ignored\@vitejs\plugin-vue\package.json" move /Y "miya_frontend\node_modules\.ignored\@vitejs\plugin-vue" "miya_frontend\node_modules\@vitejs\plugin-vue" >nul
exit /b 0

:desktop_install
echo [WARN] Dependencies not installed, running npm install...
cd /d "%~dp0miya_frontend"
set "NPM_CONFIG_REGISTRY=https://registry.npmjs.org/"
set "npm_config_registry=https://registry.npmjs.org/"
if exist "package-lock.json" (
    findstr /I "registry.npmmirror.com" package-lock.json >nul 2>&1
    if not errorlevel 1 (
        echo [WARN] Detected stale registry.npmmirror.com lockfile; regenerating it from npmjs.
        move /Y "package-lock.json" "package-lock.json.bak" >nul 2>&1
    )
)
call npm install --registry=https://registry.npmjs.org/ --loglevel=info --foreground-scripts --legacy-peer-deps
if errorlevel 1 (
    echo [ERROR] Dependency install failed!
    cd /d "%~dp0"
    goto :restart
)
goto :desktop_rebuild

:desktop_rebuild
cd /d "%~dp0miya_frontend"
echo [INFO] Downloading Electron and esbuild binaries...
if exist "node_modules\electron\install.js" (node node_modules\electron\install.js) else if exist "node_modules\.ignored\electron\install.js" (node node_modules\.ignored\electron\install.js)
if exist "node_modules\esbuild\install.js" (node node_modules\esbuild\install.js) else if exist "node_modules\.ignored\esbuild\install.js" (node node_modules\.ignored\esbuild\install.js)
cd /d "%~dp0"
goto :desktop_launch

:desktop_launch

echo Starting Electron desktop app...
echo   Start backend separately (start.bat 2)
:: Run the dev steps directly so a broken global npm shim cannot prevent launch.
:: The dependency check above guarantees the local Vite/esbuild packages exist.
start "MIYA Desktop" cmd /c "set MIYA_NO_BACKEND=1 && cd /d %~dp0miya_frontend && node scripts/generate-audio-manifest.mjs && node scripts/esbuild-electron.mjs && node node_modules/vite/bin/vite.js"
echo.
echo [OK] Desktop app launched
timeout /t 2 >nul
goto :restart

:: ============================================================
:all
cls
echo.
echo ================================================================================
echo   MIYA All-in-One
echo ================================================================================
echo.

:: Daemon (background)
echo [1/3] Starting Daemon (background)...
start "MIYA Daemon" /B cmd /c ""%~dp0.venv\Scripts\python.exe" run/daemon.py --api-port 9800"
timeout /t 3 >nul
echo [OK] Daemon started

:: Desktop (background)
if exist "miya_frontend\package.json" (
    echo [2/3] Starting Desktop app...
    start "MIYA Desktop" /B cmd /c "set MIYA_NO_BACKEND=1 && cd /d %~dp0miya_frontend && npm run dev"
    timeout /t 2 >nul
    echo [OK] Desktop launched
) else (
    echo [2/3] Desktop app not found, skipped
)

:: Terminal (foreground)
echo [3/3] Starting Terminal (foreground)...
echo.

call :ensure_host
start "MIYA Terminal" wt cmd /k powershell -NoProfile -ExecutionPolicy Bypass -File %~dp0tools\dsh-tui\launch_tui.ps1
timeout /t 2 >nul

echo.
echo [OK] All-in-One session ended
echo (Close Daemon/Desktop windows with Ctrl+C)
goto :restart

:: ============================================================
:exit
cls
echo.
echo ================================================================================
echo   Goodbye!
echo ================================================================================
timeout /t 1 >nul
exit /b 0

:: ============================================================
:restart
echo.
echo ================================================================================
set /p "rp=Return to menu? (Y/N): "
if /i "%rp%"=="y" goto :menu
echo Goodbye!
timeout /t 1 >nul
exit /b 0
