@echo off
echo ========================================
echo Live2D 独立窗口功能测试
echo ========================================
echo.

cd /d "%~dp0"

echo 步骤 1/2: 清理端口...
echo.
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 2^>nul') do (
    echo Killing process %%a...
    taskkill /F /PID %%a 2>nul
)
echo Port cleaned.
timeout /t 2

echo.
echo 步骤 2/2: 启动开发服务器...
echo.
echo 提示：
echo 1. 应用启动后，进入聊天界面
echo 2. 点击左侧工具栏的机器人图标 🤮
echo 3. 在控制面板中点击"打开窗口"
echo 4. 独立的 Live2D 窗口将显示在桌面上
echo 5. 可以拖动、调整大小、控制表情
echo.
npm run dev

pause
