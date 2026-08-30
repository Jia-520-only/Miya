#!/bin/bash

echo "========================================"
echo "    弥娅 PC端启动脚本"
echo "========================================"
echo ""

cd "$(dirname "$0")/.."

echo "[1/4] 检查Python环境..."
python3 --version
if [ $? -ne 0 ]; then
    echo "错误: 未找到Python，请先安装Python 3.11"
    exit 1
fi

echo ""
echo "[2/4] 检查依赖..."
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    echo "安装依赖..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo ""
echo "[3/4] 检查数据目录..."
mkdir -p storage/notes
mkdir -p storage/sessions
mkdir -p storage/agents
mkdir -p logs

echo ""
echo "[4/4] 启动弥娅PC端..."
python pc_ui/main.py
