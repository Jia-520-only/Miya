@echo off
echo ========================================
echo 弥娅 PC UI 安装
echo ========================================

echo.
echo [1/2] 安装 Node.js 依赖...
npm install
if %errorlevel% neq 0 (
    echo 安装依赖失败！
    pause
    exit /b 1
)

echo.
echo [2/2] 安装完成！
echo.
echo 运行以下命令启动开发服务器：
echo   npm run dev
echo.
echo 或运行：
echo   start-dev.bat
echo.

pause
