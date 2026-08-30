@echo off
chcp 65001 >nul
echo ========================================
echo         弥娅 AI 系统
echo         Miya AI System
echo ========================================
echo.

cd /d "%~dp0"

echo 正在启动弥娅系统...
echo.

python main.py

if errorlevel 1 (
    echo.
    echo 启动失败，请检查错误信息
    pause
)
