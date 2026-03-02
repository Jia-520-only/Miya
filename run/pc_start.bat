@echo off
chcp 65001 >nul
echo ========================================
echo     弥娅 PC端启动脚本
echo ========================================
echo.

cd /d "%~dp0..\"

echo [1/4] 检查Python环境...
python --version
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.11
    pause
    exit /b 1
)

echo.
echo [2/4] 检查依赖...
if not exist "venv\" (
    echo 创建虚拟环境...
    python -m venv venv
    call venv\Scripts\activate
    echo 安装依赖...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)

echo.
echo [3/4] 检查数据目录...
if not exist "storage\" mkdir storage
if not exist "storage\notes\" mkdir storage\notes
if not exist "storage\sessions\" mkdir storage\sessions
if not exist "storage\agents\" mkdir storage\agents
if not exist "logs\" mkdir logs

echo.
echo [4/4] 启动弥娅PC端...
python pc_ui/main.py

pause
