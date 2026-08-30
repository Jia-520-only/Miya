@echo off
chcp 65001 >nul
echo ========================================
echo 弥娅桌面应用 - 独立启动
echo ========================================

cd /d "%~dp0"

echo.
echo [步骤 1] 终止所有 Electron 进程...
taskkill /F /IM electron.exe /T 2>nul

echo.
echo [步骤 2] 等待 3 秒，让端口完全释放...
timeout /t 3 /nobreak >nul

echo.
echo [步骤 3] 删除旧的编译文件...
if exist "dist-electron" (
    rd /s /q "dist-electron" 2>nul
)
if exist "dist" (
    rd /s /q "dist" 2>nul
)

echo.
echo [步骤 4] 启动 Vite 开发服务器...
echo ========================================
echo.

npm run dev
