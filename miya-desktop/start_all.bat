@echo off
echo ========================================
echo 弥娅桌面应用 - 完整启动
echo ========================================

cd /d "%~dp0"

echo.
echo [步骤 1] 清理旧的编译文件...
if exist "dist-electron" (
    echo 删除 dist-electron 文件夹
    rd /s /q "dist-electron"
)
if exist "dist" (
    echo 删除 dist 文件夹
    rd /s /q "dist"
)

echo.
echo [步骤 2] 启动 Vite 开发服务器（会自动编译 preload.js）...
start "MIYA Dev Server" cmd /k "npm run dev"

echo.
echo [步骤 3] 等待服务器启动（10秒）...
timeout /t 10 /nobreak >nul

echo.
echo [步骤 4] 检查编译文件...
if not exist "dist-electron\preload.js" (
    echo [错误] preload.js 未找到！请检查控制台错误
    pause
    exit /b 1
)

if not exist "dist-electron\main.js" (
    echo [错误] main.js 未找到！请检查控制台错误
    pause
    exit /b 1
)

echo [成功] 编译文件已就绪！

echo.
echo [步骤 5] 启动 Electron...
start "MIYA Electron" cmd /k "npm run dev:electron"

echo.
echo ========================================
echo 启动完成！
echo 如果桌宠窗口无法打开，请检查：
echo 1. dist-electron\preload.js 是否存在
echo 2. 控制台是否有错误信息
echo 3. 点击"桌宠模式"按钮来打开桌宠窗口
echo ========================================

timeout /t 2 /nobreak >nul
exit
