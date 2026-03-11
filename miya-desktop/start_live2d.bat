@echo off
chcp 65001 >nul
echo ========================================
echo 启动弥娅 - Live2D完整版
echo ========================================
echo.

REM 保存当前目录
set ORIGINAL_DIR=%CD%

REM 切换到miya-desktop目录
cd /d "%~dp0"

echo 当前目录: %CD%
echo.

REM 检查package.json
if not exist "package.json" (
    echo [X] 错误: 找不到package.json
    echo 当前目录: %CD%
    echo.
    echo 请检查文件是否存在
    pause
    exit /b 1
)

echo [✓] 找到package.json
echo.

REM 检查并清理端口5173
echo [检查] 检查端口5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do (
    echo [清理] 发现进程占用端口5173，PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    echo [✓] 已终止进程
)
echo.

REM 检查node_modules和依赖版本
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

REM 检查pixi.js版本
findstr /C:"\"pixi.js\": \"^6" package.json >nul
if errorlevel 1 (
    echo [!] pixi.js版本不正确，需要6.x版本
    echo.
    echo 请运行: install_live2d_fix.bat
    pause
    exit /b 1
)
echo [✓] pixi.js版本正确 (6.x)
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
echo - 使用 window.PIXI 全局对象
echo - 模型路径: public/live2d/ht/
echo ========================================
echo.

REM 恢复原始目录
cd /d %ORIGINAL_DIR%

pause
