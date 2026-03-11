@echo off
chcp 65091 >nul
echo ========================================
echo Live2D - 强制重启（完全清理）
echo ========================================
echo.

cd /d "%~dp0"

echo [1/6] 停止所有进程...
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM electron.exe >nul 2>&1
echo [✓] 已停止所有进程
echo.

echo [2/6] 清理端口5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo [✓] 端口已清理
echo.

echo [3/6] 完全删除Vite缓存...
if exist "node_modules\.vite" (
    rmdir /s /q "node_modules\.vite"
    echo [✓] node_modules\.vite 已删除
) else (
    echo [-] node_modules\.vite 不存在
)
echo.

echo [4/6] 删除dist目录...
if exist "dist" (
    rmdir /s /q "dist"
    echo [✓] dist 已删除
)
if exist "dist-electron" (
    rmdir /s /q "dist-electron"
    echo [✓] dist-electron 已删除
)
echo.

echo [5/6] 验证pixi.js版本...
findstr /C:"pixi.js.*6.5.10" package.json >nul
if errorlevel 1 (
    echo [!] pixi.js版本不正确！
    findstr "pixi.js" package.json
    pause
    exit /b 1
)
echo [✓] pixi.js@6.5.10 确认
echo.

echo [6/6] 启动开发服务器（强制重新构建）...
set VITE_FORCE_OPTIMIZE_DEPS=true
start "Miya-Vite" cmd /k "cd /d %CD% && set VITE_FORCE_OPTIMIZE_DEPS=true && npm run dev"

echo [等待] 等待服务器启动（15秒）...
timeout /t 15 /nobreak >nul

echo [启动] Electron应用...
start "Miya-Electron" cmd /k "cd /d %CD% && npm run dev:electron"

echo.
echo ========================================
echo 强制重启完成！
echo.
echo 关键修复：
echo 1. 完全删除了 Vite 缓存
echo 2. 设置了 VITE_FORCE_OPTIMIZE_DEPS=true
echo 3. 强制重新构建所有依赖
echo 4. 验证了 pixi.js 版本
echo.
echo 现在应该可以正常使用Live2D了！
echo ========================================
echo.
pause
