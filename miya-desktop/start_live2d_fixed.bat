@echo off
chcp 65001 >nul
echo ========================================
echo 启动弥娅 - Live2D完整版（已修复）
echo ========================================
echo.

cd /d "%~dp0"

echo 当前目录: %CD%
echo.

REM 检查package.json
if not exist "package.json" (
    echo [X] 错误: 找不到package.json
    pause
    exit /b 1
)

echo [✓] 找到package.json
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
    echo [✓] 依赖安装完成
    echo.
)

REM 检查并清理端口5173
echo [检查] 检查端口5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do (
    taskkill /F /PID %%a >nul 2>&1
    echo [清理] 已终止进程 %%a
)
echo.

REM 检查pixi.js版本（简单检查）
findstr /C:"pixi.js" package.json | findstr /C:"6.5.10" >nul
if errorlevel 1 (
    echo [!] pixi.js版本可能不正确
    echo 当前配置:
    findstr /C:"pixi.js" package.json
    echo.
    echo 请运行: fix_pixi.bat
    pause
    exit /b 1
)
echo [✓] pixi.js版本正确 (6.5.10)
echo.

REM 清理Vite缓存
if exist "node_modules\.vite" (
    echo [清理] 清理Vite缓存...
    rmdir /s /q "node_modules\.vite"
    echo [✓] 缓存已清理
)
echo.

REM 启动开发服务器
echo [启动] Vite开发服务器...
start "Miya-Vite" cmd /k "cd /d %CD% && npm run dev"

REM 等待服务器启动
echo [等待] 等待开发服务器启动（10秒）...
timeout /t 10 /nobreak >nul

REM 启动Electron
echo [启动] Electron应用...
start "Miya-Electron" cmd /k "cd /d %CD% && npm run dev:electron"

echo.
echo ========================================
echo 启动完成！
echo.
echo Live2D完整版功能：
echo 1. 真正的Live2D 3D渲染
echo 2. 8种表情切换
echo 3. 实时情绪响应
echo.
echo 技术细节：
echo - pixi.js@6.5.10 (兼容 pixi-live2d-display@0.4.0)
echo - live2dcubismcore.min.js 核心库
echo - window.PIXI 全局对象
echo - 模型路径: public/live2d/ht/
echo ========================================
echo.
pause
