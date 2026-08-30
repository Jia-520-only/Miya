@echo off
chcp 65001 >nul
echo ========================================
echo Live2D 完整版 - 重启修复
echo ========================================
echo.

cd /d "%~dp0"

echo [1/5] 清理端口5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo [✓] 端口已清理
echo.

echo [2/5] 清理Vite缓存...
if exist "node_modules\.vite" (
    rmdir /s /q "node_modules\.vite"
    echo [✓] Vite缓存已清理
) else (
    echo [-] Vite缓存不存在
)
echo.

echo [3/5] 清理dist目录...
if exist "dist" (
    rmdir /s /q "dist"
    echo [✓] dist已清理
)
if exist "dist-electron" (
    rmdir /s /q "dist-electron"
    echo [✓] dist-electron已清理
)
echo.

echo [4/5] 验证依赖版本...
findstr /C:"pixi.js.*6.5.10" package.json >nul
if errorlevel 1 (
    echo [!] pixi.js版本不正确
    findstr "pixi.js" package.json
    pause
    exit /b 1
)
echo [✓] pixi.js@6.5.10 确认
echo.

echo [5/5] 启动开发服务器...
start "Miya-Vite" cmd /k "cd /d %CD% && npm run dev"

echo [等待] 等待服务器启动（12秒）...
timeout /t 12 /nobreak >nul

echo [启动] Electron应用...
start "Miya-Electron" cmd /k "cd /d %CD% && npm run dev:electron"

echo.
echo ========================================
echo 重启完成！
echo.
echo 修复内容：
echo 1. 已清理所有缓存
echo 2. 已更新 vite.config.ts
echo 3. 已添加 pixi.js 和 pixi-live2d-display 到 optimizeDeps
echo 4. 已定义 'global': 'globalThis'
echo.
echo 现在应该可以正常使用Live2D了！
echo ========================================
echo.
pause
