@echo off
chcp 65001 >nul
title MIYA 记忆备份
echo.
echo ============================================
echo   MIYA 弥娅记忆备份
echo ============================================
echo.
echo 请准备好 U盘 / 移动硬盘，并确认已关闭弥娅。
echo.
set /p DEST="请输入备份目标盘符或目录 (如 E:\MiyaBackup，直接回车默认 E:\MiyaBackup): "
if "%DEST%"=="" set DEST=E:\MiyaBackup
echo.
echo 备份模式:
echo   [1] 核心模式 (记忆+对话+配置，约400MB)  -- 推荐
echo   [2] 完整模式 (含唱歌工程/下载文件/模型，约数GB)
echo.
set /p MODE="请选择 (1/2，直接回车默认1): "
if "%MODE%"=="" set MODE=1
if "%MODE%"=="1" (
    set MODEARGS=-Mode Core
) else (
    set MODEARGS=-Mode Full
)

echo.
echo 开始备份到 %DEST% ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup_miya_memory.ps1" -Destination "%DEST%" %MODEARGS%
echo.
pause
