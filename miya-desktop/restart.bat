@echo off
echo ========================================
echo 重启弥娅桌面应用
echo ========================================

echo.
echo [1/3] 停止所有 Electron 和 Vite 进程...
taskkill /F /IM electron.exe 2>nul
taskkill /F /IM node.exe 2>nul

echo.
echo [2/3] 清除 Vite 缓存...
if exist "node_modules\.vite" (
    rmdir /s /q "node_modules\.vite"
    echo 已清除 Vite 缓存
)

echo.
echo [3/3] 重新启动开发服务器...
echo.
echo 提示：请按 Ctrl+C 停止服务器
echo.

npm run dev

pause
