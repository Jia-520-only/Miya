#!/bin/bash

echo "========================================"
echo "弥娅桌面端 - 依赖安装"
echo "========================================"
echo ""

echo "[1/2] 安装 Node.js 依赖..."
npm install
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 依赖安装失败!"
    exit 1
fi

echo ""
echo "[2/2] 创建资源目录..."
mkdir -p resources/live2d
mkdir -p resources/public

echo ""
echo "✅ 安装完成!"
echo ""
echo "下一步:"
echo "  1. 确保弥娅后端已启动 (cd .. && python run/main.py)"
echo "  2. 运行 npm run dev 启动桌面端"
echo ""
