@echo off
chcp 65001 >nul
echo ========================================
echo Live2D SDK 单独安装脚本
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查环境...
if not exist "package.json" (
    echo ❌ 错误: 未找到 package.json
    pause
    exit /b 1
)
echo ✓ package.json 存在
echo.

echo [2/3] 配置 npm...
set npm_config_cache=%~dp0.npm-cache
set npm_config_prefix=%~dp0.npm-global
echo ✓ npm 缓存和前缀已设置
echo.

echo [3/3] 安装 Live2D SDK...
echo 安装 pixi.js@^7.3.2...
call npm install --save pixi.js@^7.3.2 --no-save --legacy-peer-deps

echo.
echo 安装 pixi-live2d-display@^0.4.0...
call npm install --save pixi-live2d-display@^0.4.0 --no-save --legacy-peer-deps

echo.
echo ========================================
echo 验证安装...
echo ========================================

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
if exist "node_modules\pixi.js" (
    if exist "node_modules\pixi-live2d-display" (
        echo ========================================
        echo ✅ Live2D SDK 安装成功！
        echo ========================================
    ) else (
        echo ========================================
        echo ❌ 部分安装失败
        echo ========================================
    )
) else (
    echo ========================================
    echo ❌ 安装失败
    echo ========================================
    echo.
    echo 请尝试:
    echo 1. 以管理员身份运行
    echo 2. 手动运行: npm install
    echo 3. 使用 install_deps_fix.bat 重新安装所有依赖
)
echo.
pause
