@echo off
echo ========================================
清理端口并启动桌面应用
echo ========================================

echo.
echo [清理] 终止旧进程...
taskkill /F /IM node.exe 2>nul
taskkill /F /IM electron.exe 2>nul
taskkill /F /IM python.exe 2>nul

echo.
echo [清理] 删除旧编译文件...
cd miya-desktop
if exist "dist-electron" (
    rd /s /q "dist-electron"
    echo 已删除 dist-electron 文件夹
)

echo.
echo ========================================
启动桌面应用
echo ========================================
echo.

cd ..
python run/desktop_main.py
