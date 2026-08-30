@echo off
echo ========================================
echo 编译 Electron 文件
echo ========================================

cd /d "%~dp0"

echo.
echo [1/3] 清理旧的编译文件...
if exist "dist-electron" (
    echo 删除 dist-electron 文件夹
    rd /s /q "dist-electron"
)
mkdir dist-electron

echo.
echo [2/3] 编译 main.js...
call npx vite build --config vite.config.ts --mode electron

echo.
echo [3/3] 检查编译结果...
if exist "dist-electron\main.js" (
    echo ✅ main.js 编译成功
) else (
    echo ❌ main.js 编译失败
)

if exist "dist-electron\preload.js" (
    echo ✅ preload.js 编译成功
) else (
    echo ❌ preload.js 编译失败
)

echo.
echo ========================================
echo 编译完成！
echo ========================================
