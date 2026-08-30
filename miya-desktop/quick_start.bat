@echo off
echo ========================================
echo 弥娅桌面应用 - 快速启动
echo ========================================

cd /d "%~dp0"

echo.
echo 步骤 1/2: 编译 Electron 文件...
echo.

:: 检查 dist-electron 是否存在
if not exist "dist-electron\preload.js" (
    echo [信息] 需要编译 Electron 文件...
    echo.
    echo 启动 Vite 开发服务器（会自动编译）...
    echo 请等待编译完成（约10-20秒）
    echo.
    start /min cmd /c "npm run dev && timeout /t 5 && exit"
    timeout /t 15 >nul
    echo [完成] 编译完成
) else (
    echo [跳过] Electron 文件已存在
)

echo.
echo 步骤 2/2: 启动 Electron 应用...
echo.
npm run dev:electron

:end
echo.
pause
