@echo off
chcp 65001 >nul
echo ========================================
echo 弥娅桌面端 - 快速刷新UI
echo ========================================
echo.

echo 正在清理Vite缓存...
if exist "node_modules\.vite" (
    rmdir /s /q "node_modules\.vite"
    echo ✓ 已清理: node_modules\.vite
) else (
    echo - 缓存目录不存在,跳过
)

if exist ".vite" (
    rmdir /s /q ".vite"
    echo ✓ 已清理: .vite
) else (
    echo - 缓存目录不存在,跳过
)

echo.
echo 停止现有进程...
taskkill /F /IM electron.exe 2>nul
taskkill /F /IM node.exe 2>nul
echo ✓ 已停止进程
echo.
timeout /t 2 /nobreak >nul

echo ========================================
echo 准备启动应用!
echo ========================================
echo.
echo UI已更新,包含:
echo   - 动态科技感背景(网格+光球)
echo   - 半透明毛玻璃效果
echo   - 更紧凑的布局
echo   - UI透明度控制
echo.
echo 请运行以下命令启动应用:
echo   npm run dev:all
echo.
echo 启动后,如果效果没有自动显示,请:
echo   1. 按 Ctrl+R 刷新页面
echo   2. 或按 Ctrl+Shift+R 强制刷新
echo.
pause
