@echo off
chcp 65001 >nul
echo ========================================
echo 弥娅依赖修复安装脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] 检查环境...
if not exist "package.json" (
    echo ❌ 错误: 未找到 package.json 文件
    pause
    exit /b 1
)
echo ✓ package.json 存在
echo.

echo [2/4] 配置 npm 缓存目录...
call npm config set cache "%~dp0.npm-cache" --global
echo ✓ npm 缓存已设置为本地目录
echo.

echo [3/4] 清理旧的 node_modules...
if exist "node_modules" (
    echo 删除旧的 node_modules...
    rmdir /s /q node_modules 2>nul
    timeout /t 2 >nul
)
echo ✓ 清理完成
echo.

echo [4/4] 安装所有依赖...
echo 这可能需要几分钟时间...
echo.

call npm install

if %errorlevel% neq 0 (
    echo.
    echo ❌ 安装失败！
    echo.
    echo 请尝试:
    echo 1. 以管理员身份运行此脚本
    echo 2. 手动运行: npm install
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo 验证安装...
echo ========================================

echo.
echo 检查 Live2D SDK:
if exist "node_modules\pixi.js" (
    echo ✓ pixi.js 已安装
) else (
    echo ✗ pixi.js 未安装
)

if exist "node_modules\pixi-live2d-display" (
    echo ✓ pixi-live2d-display 已安装
) else (
    echo ✗ pixi-live2d-display 未安装
)

echo.
echo 检查其他依赖:
if exist "node_modules\vue" (
    echo ✓ Vue 已安装
) else (
    echo ✗ Vue 未安装
)

if exist "node_modules\electron" (
    echo ✓ Electron 已安装
) else (
    echo ✗ Electron 未安装
)

echo.
echo ========================================
echo ✅ 依赖安装完成！
echo ========================================
echo.
echo 下一步:
echo 运行 npm run dev 启动弥娅桌面应用
echo.
pause
