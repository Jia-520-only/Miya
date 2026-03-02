@echo off
chcp 65001 >nul
echo ========================================
echo         弥娅 QQ 机器人
echo         Miya QQ Bot
echo ========================================
echo.

cd /d "%~dp0"

echo 正在启动弥娅QQ机器人...
echo.

python qq_main.py

if errorlevel 1 (
    echo.
    echo 启动失败，请检查错误信息
    pause
)
