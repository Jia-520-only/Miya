@echo off
chcp 65001 >nul
echo ========================================
echo       弥娅 Web 前端
echo       Miya Web UI
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/5] 检查Python环境...
if not exist "venv\" (
    echo 错误: 未找到虚拟环境，请先运行 install.bat
    pause
    exit /b 1
)

set PYTHON_EXE=%~dp0..\venv\Scripts\python.exe

echo.
echo [2/5] 检查配置文件...
if not exist "config\.env" (
    echo 错误: 配置文件不存在 config\.env
    pause
    exit /b 1
)

echo.
echo [3/5] 清理被占用的端口...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo    发现进程 %%a 占用端口 8000，正在清理...
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo    发现进程 %%a 占用端口 3000，正在清理...
    taskkill /F /PID %%a >nul 2>&1
)
echo    ✓ 端口清理完成

echo.
echo [4/5] 检查Node.js环境...
node --version
if errorlevel 1 (
    echo 警告: 未找到Node.js，请先安装Node.js 18+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

echo.
echo [5/5] 检查Web前端依赖...
cd miya-pc-ui
if not exist "node_modules\" (
    echo 首次启动，正在安装依赖...
    call npm install
    if errorlevel 1 (
        echo 错误: 依赖安装失败
        pause
        exit /b 1
    )
)

echo.
echo [6/6] 启动服务...
echo.
echo 后端API服务启动中...
echo 访问地址: http://localhost:8000
echo.

cd /d "%~dp0.."
start /B "%PYTHON_EXE%" run/web_main.py

echo 等待后端启动...
timeout /t 3 /nobreak

echo 前端开发服务器启动中...
echo 访问地址: http://localhost:3000
echo.

cd miya-pc-ui
call npm run dev:web

pause
