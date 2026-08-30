@echo off
echo ========================================
echo 强制刷新UI - 清理Vite缓存
echo ========================================
echo.

echo 1. 停止Electron进程...
taskkill /F /IM electron.exe 2>nul
taskkill /F /IM node.exe 2>nul
echo 等待进程结束...
timeout /t 3 /nobreak >nul

echo.
echo 2. 清理Vite缓存...
if exist "node_modules\.vite" (
    rmdir /s /q "node_modules\.vite"
    echo 已清理: node_modules\.vite
) else (
    echo 缓存目录不存在,跳过
)

if exist ".vite" (
    rmdir /s /q ".vite"
    echo 已清理: .vite
) else (
    echo 缓存目录不存在,跳过
)

echo.
echo ========================================
echo 缓存清理完成!
echo ========================================
echo.
echo 请重新运行以下命令启动应用:
echo   npm run dev:all
echo.
pause
