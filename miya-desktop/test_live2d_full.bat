@echo off
chcp 65001 >nul
echo ========================================
echo 弥娅 - Live2D完整版测试
echo ========================================
echo.

cd /d "%~dp0miya-desktop"

echo 正在启动开发服务器...
echo.

REM 检查node_modules
if not exist "node_modules" (
    echo [!] node_modules未找到，正在安装依赖...
    call npm install
    if errorlevel 1 (
        echo [X] 依赖安装失败！
        pause
        exit /b 1
    )
)

REM 启动开发服务器
echo [启动] Vite开发服务器...
start cmd /k "npm run dev"

REM 等待服务器启动
echo [等待] 等待开发服务器启动...
timeout /t 8 /nobreak >nul

REM 启动Electron
echo [启动] Electron应用...
start cmd /k "npm run dev:electron"

echo.
echo ========================================
echo 启动完成！
echo.
echo 请注意：
echo 1. Live2D完整版需要WebGL支持
echo 2. 模型文件位于 public/live2d/ht/ 目录
echo 3. 如果遇到加载问题，请检查控制台日志
echo ========================================
echo.
pause
