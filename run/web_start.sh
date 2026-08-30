#!/bin/bash

echo "========================================"
echo "       弥娅 Web 前端"
echo "       Miya Web UI"
echo "========================================"
echo ""

cd "$(dirname "$0")/.."

# 检查 Python 环境
echo "[1/5] 检查Python环境..."
if [ ! -d "venv" ]; then
    echo "错误: 未找到虚拟环境，请先运行 install.sh"
    exit 1
fi

PYTHON_EXE="./venv/bin/python"

# 检查配置文件
echo ""
echo "[2/5] 检查配置文件..."
if [ ! -f "config/.env" ]; then
    echo "错误: 配置文件不存在 config/.env"
    exit 1
fi

# 检查 Node.js 环境
echo ""
echo "[3/5] 检查Node.js环境..."
if ! command -v node &> /dev/null; then
    echo "警告: 未找到Node.js，请先安装Node.js 18+"
    echo "下载地址: https://nodejs.org/"
    exit 1
fi
node --version

# 检查 Web 前端依赖
echo ""
echo "[4/5] 检查Web前端依赖..."
cd miya-pc-ui
if [ ! -d "node_modules" ]; then
    echo "首次启动，正在安装依赖..."
    npm install
    if [ $? -ne 0 ]; then
        echo "错误: 依赖安装失败"
        exit 1
    fi
fi

# 启动服务
echo ""
echo "[5/5] 启动服务..."
echo ""
echo "后端API服务启动中..."
echo "访问地址: http://localhost:8000"
echo ""

cd ../
$PYTHON_EXE run/web_main.py &
BACKEND_PID=$!

echo "等待后端启动..."
sleep 3

echo "前端开发服务器启动中..."
echo "访问地址: http://localhost:5173"
echo ""

cd miya-pc-ui
npm run dev:web

# 清理
kill $BACKEND_PID 2>/dev/null
