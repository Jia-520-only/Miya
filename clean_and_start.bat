@echo off
echo 正在清理端口...
taskkill /F /IM node.exe 2>nul
taskkill /F /IM electron.exe 2>nul
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
echo 端口已清理
echo.
echo 启动桌面应用...
python run/desktop_main.py
