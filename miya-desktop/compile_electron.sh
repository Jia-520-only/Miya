#!/bin/bash

echo "========================================"
echo "编译 Electron 主进程和 Preload"
echo "========================================"

cd "$(dirname "$0")"

echo ""
echo "检查依赖..."
if [ ! -d "node_modules" ]; then
    echo "[错误] node_modules 不存在，请先运行 npm install"
    exit 1
fi

echo ""
echo "编译 Electron 主进程和 Preload..."
npx electron-vite build --mode development

if [ $? -ne 0 ]; then
    echo "[错误] 编译失败"
    exit 1
fi

echo ""
echo "[成功] 编译完成"
echo ""
echo "dist-electron 目录内容："
ls -la dist-electron/

echo ""
