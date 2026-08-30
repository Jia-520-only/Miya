#!/bin/bash

echo "========================================"
echo "  弥娅系统 - 首次初始化工具"
echo "========================================"
echo

echo "正在检查系统状态..."

# 检查是否存在鉴权数据
if [ -f "data/auth/users.json" ]; then
    echo "[√] 鉴权系统已初始化"
    echo
    echo "当前用户："
    python -c "import json; data=json.load(open('data/auth/users.json', encoding='utf-8')); [print(f'  - {u[\"user_id\"]} (平台: {u.get(\"platform\", \"unknown\")})') for u in data.get('users', [])]"
    echo
else
    echo "[!] 鉴权系统未初始化"
    echo
    echo "正在初始化鉴权系统..."
    python init_auth.py
    echo
fi

echo "========================================"
echo "  初始化完成"
echo "========================================"
echo
echo "现在您可以启动弥娅系统了！"
echo
echo "注意："
echo "  1. 默认终端用户: terminal_default (管理员权限)"
echo "  2. 如需添加新用户，请运行: python init_auth.py"
echo "  3. 详见: AUTH_USAGE_GUIDE.md"
echo
