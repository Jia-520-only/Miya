@echo off
chcp 65001 >nul
echo ========================================
echo 弥娅 Live2D SDK 安装脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查当前目录...
if not exist "package.json" (
    echo ❌ 错误: 未找到 package.json 文件
    echo 请确保在 miya-desktop 目录下运行此脚本
    pause
    exit /b 1
)
echo ✓ package.json 文件存在
echo.

echo [2/3] 安装 Live2D SDK 依赖包...
echo 正在安装 pixi.js@^7.3.2 和 pixi-live2d-display@^0.4.0
echo.

call npm install pixi.js@^7.3.2 pixi-live2d-display@^0.4.0

if %errorlevel% neq 0 (
    echo.
    echo ❌ 安装失败！
    echo.
    echo 可能的解决方案:
    echo 1. 以管理员身份运行此脚本
    echo 2. 关闭其他占用 node_modules 的程序
    echo 3. 检查网络连接
    echo 4. 尝试清理 npm 缓存: npm cache clean --force
    echo.
    pause
    exit /b 1
)

echo.
echo [3/3] 验证安装...
if exist "node_modules\pixi.js" (
    echo ✓ pixi.js 安装成功
) else (
    echo ❌ pixi.js 未找到
)

if exist "node_modules\pixi-live2d-display" (
    echo ✓ pixi-live2d-display 安装成功
) else (
    echo ❌ pixi-live2d-display 未找到
)

echo.
echo ========================================
echo ✅ Live2D SDK 安装完成！
echo ========================================
echo.
echo 下一步:
echo 1. 运行 start.bat 启动弥娅桌面应用
echo 2. Live2D 将自动加载并显示在右侧边栏
echo.
pause
