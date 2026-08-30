@echo off
chcp 65001 >nul
echo ========================================
echo 安装 Live2D 正确依赖版本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 清理旧版本依赖...
if exist "node_modules\pixi.js" (
    echo 正在删除 pixi.js 旧版本...
    rmdir /s /q "node_modules\pixi.js" 2>nul
)

echo [2/3] 安装 pixi.js@6.5.10...
call npm install pixi.js@6.5.10 --save --force
if errorlevel 1 (
    echo [X] 安装失败！
    pause
    exit /b 1
)

echo [3/3] 重新安装所有依赖...
call npm install --force
if errorlevel 1 (
    echo [X] 依赖安装失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo 安装完成！
echo ========================================
echo.
echo 已安装:
echo - pixi.js@6.5.10 (兼容 pixi-live2d-display@0.4.0)
echo - pixi-live2d-display@0.4.0
echo.
echo 请运行 start_live2d.bat 启动应用
echo ========================================
echo.
pause
