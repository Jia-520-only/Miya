@echo off
echo ========================================
echo MIYA Desktop - 启动脚本
echo ========================================

echo.
echo [提示] 如果遇到preload.js错误，请确保：
echo 1. 删除 dist-electron 文件夹
echo 2. 重新运行此脚本
echo ========================================
echo.

echo [步骤 1] 启动完整开发流程...
call npm run dev:all

pause
