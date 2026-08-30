#!/bin/bash

# 构建弥娅 Web 前端

echo "========================================"
echo "   弥娅 Web 前端构建工具"
echo "========================================"
echo ""

WEB_DIR="$(cd "$(dirname "$0")/.." && pwd)/frontend/packages/web"

if [ ! -d "$WEB_DIR" ]; then
    echo "[错误] Web 前端目录不存在: $WEB_DIR"
    exit 1
fi

echo "[1/4] 进入 Web 前端目录..."
cd "$WEB_DIR"

echo "[2/4] 检查 Node.js 和 npm..."
if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
    echo "[错误] 未找到 Node.js 或 npm"
    echo "请先安装 Node.js: https://nodejs.org/"
    exit 1
fi
echo "  Node.js: $(node --version)"
echo "  npm: $(npm --version)"

echo ""
echo "[3/4] 安装依赖..."
npm install --loglevel=info --foreground-scripts

if [ $? -ne 0 ]; then
    echo "[错误] 依赖安装失败"
    exit 1
fi

echo ""
echo "[4/4] 构建生产版本..."
npm run build

if [ $? -ne 0 ]; then
    echo "[错误] 构建失败"
    exit 1
fi

echo ""
echo "========================================"
echo "  ✅ 构建成功！"
echo "========================================"
echo ""
echo "输出目录: $WEB_DIR/dist"
echo ""
echo "现在可以启动 Web 服务了："
echo "  python webnet/web_main.py"
echo ""
