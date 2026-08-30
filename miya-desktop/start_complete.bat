@echo off
echo ========================================
echo MIYA Desktop - 完整启动流程
echo ========================================

echo.
echo [步骤 1] 清理旧的编译文件...
if exist "dist-electron" rd /s /q "dist-electron"
if exist "dist" rd /s /q "dist"

echo.
echo [步骤 2] 编译 preload 和 main...
call npm run build:electron || goto :error

echo.
echo [步骤 3] 检查编译文件...
if not exist "dist-electron\preload.js" (
    echo [错误] preload.js 未找到！
    goto :error
)
if not exist "dist-electron\main.js" (
    echo [错误] main.js 未找到！
    goto :error
)

echo [成功] 编译完成！
echo.
echo [步骤 4] 启动开发服务器...
start "MIYA Dev Server" cmd /k "npm run dev"

echo.
echo [步骤 5] 等待开发服务器启动（5秒）...
timeout /t 5 /nobreak >nul

echo.
echo [步骤 6] 启动 Electron...
start "MIYA Electron" cmd /k "npm run dev:electron"

echo.
echo ========================================
echo 启动完成！
echo 如果桌宠窗口无法打开，请检查：
echo 1. dist-electron\preload.js 是否存在
echo 2. 控制台是否有错误信息
echo ========================================

goto :end

:error
echo.
echo ========================================
echo [错误] 启动失败！
echo ========================================
pause
exit /b 1

:end
