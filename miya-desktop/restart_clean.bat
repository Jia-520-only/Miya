@echo off
echo ========================================
echo 弥娅桌面应用 - 清理重启
echo ========================================

cd /d "%~dp0"

echo.
echo [步骤 1] 查找并终止占用端口 5173 的进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    echo 终止进程 PID: %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo [步骤 2] 等待 2 秒...
timeout /t 2 /nobreak >nul

echo.
echo [步骤 3] 删除旧的编译文件...
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
