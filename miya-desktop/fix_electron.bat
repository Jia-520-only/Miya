@echo off
echo ========================================
echo 编译 Electron 文件（修复 preload.js）
echo ========================================

cd /d "%~dp0"

echo.
echo 清理旧的编译文件...
if exist "dist-electron" (
    rmdir /s /q dist-electron
    echo [完成] 已清理 dist-electron
)

echo.
echo 启动 Vite 开发服务器...
echo.
echo 注意：Vite 会自动编译 Electron 文件到 dist-electron 目录
echo 请等待编译完成后再启动 Electron
echo.

npm run dev
