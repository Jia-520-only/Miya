#!/bin/bash

echo "========================================"
echo "重启弥娅桌面应用"
echo "========================================"

echo ""
echo "[1/3] 停止所有 Electron 和 Vite 进程..."
pkill -f electron
pkill -f vite

echo ""
echo "[2/3] 清除 Vite 缓存..."
rm -rf node_modules/.vite
echo "已清除 Vite 缓存"

echo ""
echo "[3/3] 重新启动开发服务器..."
echo ""
echo "提示：请按 Ctrl+C 停止服务器"
echo ""

npm run dev
