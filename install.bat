@echo off
chcp 65001 >nul
echo ========================================
echo   弥娅 MIYA - 一键安装脚本
echo ========================================
echo.

REM 检查Python版本
echo [1/5] 检查Python版本...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到Python，请先安装Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [成功] Python版本: %PYTHON_VERSION%
echo.

REM 检查pip
echo [2/5] 检查pip...
python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] pip未安装或损坏
    pause
    exit /b 1
)
echo [成功] pip已安装
echo.

REM 创建虚拟环境
echo [3/5] 创建虚拟环境...
if exist venv (
    echo [信息] 虚拟环境已存在，跳过创建
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [成功] 虚拟环境创建成功
)
echo.

REM 激活虚拟环境并升级pip
echo [4/6] 激活虚拟环境并升级pip...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo [警告] pip升级失败，继续安装...
)
echo [成功] pip已升级到最新版本
echo.

REM 清除pip镜像配置（使用代理）
echo [5/6] 清除pip镜像配置...
pip config unset global.index-url >nul 2>&1
echo [成功] pip镜像配置已清除
echo.

REM 安装依赖
echo [6/6] 安装依赖包...
echo [信息] 这可能需要几分钟，请耐心等待...
set PYTHONIOENCODING=utf-8
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)
echo [成功] 依赖安装完成
echo.

REM 创建必要目录
echo [信息] 创建必要目录...
if not exist logs mkdir logs
if not exist data mkdir data
if not exist config mkdir config
if not exist storage mkdir storage
echo [成功] 目录创建完成
echo.

REM 复制配置文件
if not exist config\.env (
    echo [信息] 创建配置文件...
    copy config\.env.example config\.env >nul 2>&1
    echo [成功] 配置文件创建成功
) else (
    echo [信息] 配置文件已存在
)
echo.

echo ========================================
echo   安装完成！
echo ========================================
echo.
echo Next steps:
echo 1. Edit config file: config\.env
echo 2. Start MIYA: start.bat
echo.
echo Note:
echo - Configure Redis, Milvus, Neo4j before first run
echo - Modify config parameters according to your environment
echo.
pause
