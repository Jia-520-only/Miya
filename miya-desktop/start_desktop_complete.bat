@echo off
echo ========================================
弥娅桌面应用 - 完整启动
echo ========================================

cd /d "%~dp0"

echo.
echo [步骤 1] 清理旧的编译文件...
if exist "dist-electron" (
    echo 删除 dist-electron 文件夹
    rd /s /q "dist-electron"
)

echo.
echo [步骤 2] 启动开发服务器...
echo Vite 会自动编译 Electron 文件（preload.js 和 main.js）
echo.

call npm run dev
