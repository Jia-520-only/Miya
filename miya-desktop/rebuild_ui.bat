@echo off
echo ========================================
echo 弥娅桌面端 - 重新构建UI
echo ========================================
echo.

echo 1. 停止所有运行中的进程...
taskkill /F /IM electron.exe 2>nul
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul

echo 2. 清理构建缓存...
if exist "dist" rmdir /s /q "dist"
if exist "dist-electron" rmdir /s /q "dist-electron"
if exist ".vite" rmdir /s /q ".vite"

echo 3. 清理浏览器缓存...
if exist "node_modules\.vite" rmdir /s /q "node_modules\.vite"

echo 4. 重新构建...
echo 正在运行: vue-tsc && vite build && electron-builder
call npm run build

echo.
echo ========================================
echo 构建完成!
echo ========================================
echo.
echo 请重新启动应用查看效果
pause
