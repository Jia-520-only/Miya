@echo off
echo ========================================
echo 弥娅桌面应用 - 开发模式
echo ========================================

cd /d "%~dp0"

echo.
echo [清理] 删除旧的编译文件...
if exist "dist-electron" (
    echo 删除 dist-electron 文件夹
    rd /s /q "dist-electron"
)
if exist "dist" (
    echo 删除 dist 文件夹
    rd /s /q "dist"
)

echo.
echo ========================================
echo 启动 Vite 开发服务器...
echo ========================================
echo 注意：Vite 会自动编译 Electron 文件（main.js 和 preload.js）
echo.

call npm run dev
