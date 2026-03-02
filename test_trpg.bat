@echo off
chcp 65001 > nul
echo.
echo ================================================
echo 弥娅 TRPG 跑团系统测试
echo ================================================
echo.
echo 选择测试模式:
echo   1. 完整测试
echo   2. 仅测试骰子系统
echo   0. 退出
echo.
set /p choice="请选择 (0-2): "

if "%choice%"=="1" (
    echo.
    echo 运行完整测试...
    echo.
    python test_trpg_system.py
) else if "%choice%"=="2" (
    echo.
    echo 仅测试骰子系统...
    echo.
    python test_trpg_system.py --dice-only
) else if "%choice%"=="0" (
    exit /b 0
) else (
    echo.
    echo 无效选择！
    exit /b 1
)

echo.
echo ================================================
echo 测试完成！
echo ================================================
pause
