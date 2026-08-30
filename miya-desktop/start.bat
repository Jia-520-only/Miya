@echo off
chcp 65001 >nul
echo ========================================
echo     弥娅桌面应用
echo     Miya Desktop App
echo ========================================
echo.

cd /d "%~dp0"

echo 正在启动开发环境...
echo.

:: 检查 node_modules
if not exist "node_modules\" (
    echo [INFO] node_modules 不存在，正在安装依赖...
    call npm install
    if errorlevel 1 (
        echo.
        echo 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
)

:: 启动开发服务器
npm run dev

if errorlevel 1 (
    echo.
    echo 启动失败，请检查错误信息
    pause
)
