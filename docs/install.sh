#!/bin/bash

# 弥娅 MIYA - 一键安装脚本

echo "========================================"
echo "  弥娅 MIYA - 一键安装脚本"
echo "========================================"
echo ""

# 检查Python版本
echo "[1/5] 检查Python版本..."
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python3，请先安装Python 3.10+"
    echo "下载地址: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "[成功] Python版本: $PYTHON_VERSION"
echo ""

# 检查pip
echo "[2/5] 检查pip..."
if ! command -v pip3 &> /dev/null; then
    echo "[错误] pip3未安装"
    exit 1
fi
echo "[成功] pip3已安装"
echo ""

# 创建虚拟环境
echo "[3/5] 创建虚拟环境..."
if [ -d "venv" ]; then
    echo "[信息] 虚拟环境已存在，跳过创建"
else
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[错误] 创建虚拟环境失败"
        exit 1
    fi
    echo "[成功] 虚拟环境创建成功"
fi
echo ""

# 激活虚拟环境并升级pip
echo "[4/6] 激活虚拟环境并升级pip..."
source venv/bin/activate
pip install --upgrade pip
if [ $? -ne 0 ]; then
    echo "[警告] pip升级失败，继续安装..."
fi
echo "[成功] pip已升级到最新版本"
echo ""

# 清除pip镜像配置（使用代理）
echo "[5/6] 清除pip镜像配置..."
pip config unset global.index-url >/dev/null 2>&1 || true
echo "[成功] pip镜像配置已清除"
echo ""

# 安装依赖
echo "[6/6] 安装依赖包..."
echo "[信息] 这可能需要几分钟，请耐心等待..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[错误] 依赖安装失败"
    exit 1
fi
echo "[成功] 依赖安装完成"
echo ""

# 创建必要目录
echo "[信息] 创建必要目录..."
mkdir -p logs data config storage
echo "[成功] 目录创建完成"
echo ""

# 复制配置文件
if [ ! -f "config/.env" ]; then
    echo "[信息] 创建配置文件..."
    cp config/.env.example config/.env 2>/dev/null || true
    echo "[成功] 配置文件创建成功"
else
    echo "[信息] 配置文件已存在"
fi
echo ""

echo "========================================"
echo "  安装完成！"
echo "========================================"
echo ""
echo "下一步操作："
echo "1. 编辑配置文件: config/.env"
echo "2. 启动弥娅: ./start.sh"
echo ""
echo "注意事项："
echo "- 首次运行前请先配置Redis、Milvus、Neo4j等服务"
echo "- 配置文件中的各项参数根据实际情况修改"
echo ""
