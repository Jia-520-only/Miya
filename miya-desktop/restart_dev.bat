@echo off
echo ========================================
echo 弥娅桌面应用 - 重新启动开发环境
echo ========================================
echo.

cd /d "%~dp0"

echo [步骤 1] 停止所有运行中的进程...
taskkill /F /IM electron.exe 2>nul
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo [步骤 2] 清理编译输出目录...
if exist "dist-electron" (
    echo 删除 dist-electron 目录...
    rmdir /s /q dist-electron
)
if exist "dist" (
    echo 删除 dist 目录...
    rmdir /s /q dist
)

echo.
echo [步骤 3] 安装依赖（如果需要）...
if not exist "node_modules" (
    echo node_modules 不存在，正在安装依赖...
    call npm install
)

echo.
echo [步骤 4] 启动 Vite 开发服务器...
echo 注意：Vite 会自动编译 Electron 文件（main.js 和 preload.js）
echo 请等待 Vite 启动完成...
echo.

call npm run dev

echo.
echo [等待] 开发服务器运行中...
echo 如果需要手动启动 Electron，请在另一个窗口运行: npm run dev:electron
echo.

pause
