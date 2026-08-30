@echo off
echo ========================================
echo 强制清除缓存并重启
echo ========================================

echo.
echo [1/4] 停止所有进程...
taskkill /F /IM electron.exe 2>nul
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo [2/4] 清除所有缓存...
if exist "node_modules\.vite" (
    rmdir /s /q "node_modules\.vite"
    echo - 已清除 Vite 缓存
)
if exist "dist" (
    rmdir /s /q "dist"
    echo - 已清除 dist 目录
)
if exist "dist-electron" (
    rmdir /s /q "dist-electron"
    echo - 已清除 dist-electron 目录
)

echo.
echo [3/4] 重新构建 Electron 进程...
call npm run build:electron
if errorlevel 1 (
    echo 构建失败！请检查错误信息
    pause
    exit /b 1
)

echo.
echo [4/4] 启动开发服务器...
echo.
echo ========================================
echo 应用已启动，请测试以下内容：
echo 1. 点击桌宠按钮
echo 2. 再次点击桌宠按钮
echo 3. 查看控制台日志
echo 4. 检查 UI 是否更新
echo ========================================
echo.

npm run dev

pause
