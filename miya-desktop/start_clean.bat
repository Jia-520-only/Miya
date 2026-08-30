@echo off
chcp 65001 >nul
echo ========================================
echo 弥娅桌面应用 - 清理并启动
echo ========================================

cd /d "%~dp0"

echo.
echo [步骤 1] 终止所有 Node.js 进程...
taskkill /F /IM node.exe /T 2>nul

echo.
echo [步骤 2] 等待 3 秒，让端口完全释放...
timeout /t 3 /nobreak >nul

echo.
echo [步骤 3] 删除旧的编译文件...
if exist "dist-electron" (
    echo 删除 dist-electron 文件夹
    rd /s /q "dist-electron" 2>nul
)
if exist "dist" (
    echo 删除 dist 文件夹
    rd /s /q "dist" 2>nul
)

echo.
echo [步骤 4] 启动 Vite 开发服务器...
echo ========================================
echo.

call npm run dev
