@echo off
chcp 65001 >nul
echo ========================================
echo 修复 pixi.js 版本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] 检查当前版本...
findstr "pixi.js" package.json
echo.

echo [2/4] 删除旧的pixi.js...
if exist "node_modules\pixi.js" (
    rmdir /s /q "node_modules\pixi.js"
    echo 已删除 node_modules\pixi.js
) else (
    echo 未找到 node_modules\pixi.js
)
echo.

echo [3/4] 安装 pixi.js@6.5.10...
call npm uninstall pixi.js
call npm install pixi.js@6.5.10 --save --legacy-peer-deps
if errorlevel 1 (
    echo [X] 安装失败！
    pause
    exit /b 1
)
echo.

echo [4/4] 验证安装...
findstr "pixi.js" package.json
echo.

echo ========================================
echo 修复完成！
echo ========================================
echo.
echo 现在可以运行: start_live2d.bat
echo.
pause
