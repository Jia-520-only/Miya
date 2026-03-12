"""
初始化用户权限配置
运行此脚本可以快速设置初始用户和权限组
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from webnet.AuthNet.permission_core import PermissionCore


def init_auth_system():
    """初始化鉴权系统"""

    # 创建数据目录
    auth_dir = Path("data/auth")
    auth_dir.mkdir(parents=True, exist_ok=True)

    # 初始化权限核心
    permission_core = PermissionCore()

    # 检查是否已有数据
    users_data = permission_core.load_users()
    groups_data = permission_core.load_groups()

    if users_data.get("users") and groups_data.get("groups"):
        print("鉴权系统已初始化，数据如下：")
        print(f"  用户数: {len(users_data['users'])}")
        print(f"  权限组数: {len(groups_data['groups'])}")
        print()
        print("现有用户：")
        for user in users_data['users']:
            print(f"  - {user['user_id']} (平台: {user.get('platform', 'unknown')})")
        return

    print("初始化鉴权系统...")

    # 1. 创建默认权限组
    default_groups = {
        "Default": {
            "name": "Default",
            "description": "默认权限组 - 基础权限",
            "permissions": [
                "tool.web_search",
                "tool.get_current_time",
                "memory.read",
                "memory.write",
                "knowledge.search"
            ]
        },
        "Admin": {
            "name": "Admin",
            "description": "管理员权限组 - 拥有所有权限",
            "permissions": ["*.*"]
        },
        "Terminal": {
            "name": "Terminal",
            "description": "终端用户组 - 终端基础权限",
            "permissions": [
                "tool.terminal.execute",
                "tool.web_search",
                "tool.get_current_time",
                "memory.read",
                "memory.write"
            ]
        }
    }

    # 保存权限组
    permission_core.save_groups({"groups": default_groups})
    print("✓ 已创建默认权限组: Default, Admin, Terminal")

    # 2. 创建默认用户
    default_users = [
        {
            "user_id": "terminal_default",
            "username": "默认终端用户",
            "platform": "terminal",
            "permission_groups": ["Admin"],
            "permissions": [],
            "created_at": "2026-03-11T00:00:00"
        },
        {
            "user_id": "web_default",
            "username": "默认Web用户",
            "platform": "web",
            "permission_groups": ["Default"],
            "permissions": [],
            "created_at": "2026-03-11T00:00:00"
        }
    ]

    # 保存用户
    permission_core.save_users({"users": default_users})
    print("✓ 已创建默认用户: terminal_default, web_default")

    print()
    print("初始化完成！")
    print()
    print("用户信息：")
    for user in default_users:
        print(f"  - {user['user_id']}")
        print(f"    用户名: {user['username']}")
        print(f"    平台: {user['platform']}")
        print(f"    权限组: {', '.join(user['permission_groups'])}")
        print()

    print("使用说明：")
    print("  1. 用户ID格式: platform_id (如: terminal_default, qq_123, web_user456)")
    print("  2. 每个用户可以属于多个权限组")
    print("  3. 权限组定义了用户可以访问的功能")
    print("  4. Admin组拥有 *.* 权限（所有权限）")
    print()


def add_user_interactive():
    """交互式添加用户"""
    from webnet.AuthNet.tools.add_user import AddUserTool
    import asyncio

    print("\n=== 交互式添加用户 ===")

    user_id = input("请输入用户ID（格式: platform_id，如: qq_123, web_user456）: ").strip()
    if not user_id:
        print("用户ID不能为空！")
        return

    username = input(f"请输入用户名（默认: {user_id}）: ").strip() or user_id
    platform = input("请输入平台（qq/web/desktop/terminal，默认: terminal）: ").strip() or "terminal"

    print("\n可用权限组:")
    print("  Default - 默认权限组 - 基础权限")
    print("  Admin - 管理员权限组 - 拥有所有权限")
    print("  Terminal - 终端用户组 - 终端基础权限")

    groups_input = input("请输入权限组（多个用逗号分隔，默认: Default）: ").strip()
    permission_groups = [g.strip() for g in groups_input.split(",")] if groups_input else ["Default"]

    # 创建工具实例
    tool = AddUserTool()

    # 构建参数
    args = {
        "user_id": user_id,
        "username": username,
        "platform": platform,
        "permission_groups": permission_groups
    }

    # 执行
    try:
        result = asyncio.run(tool.execute(args, None))
        print(f"\n执行结果: {result}")
    except Exception as e:
        print(f"\n执行失败: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("弥娅鉴权系统初始化工具")
    print("=" * 60)
    print()

    choice = input("请选择操作:\n  1. 初始化鉴权系统（创建默认用户和权限组）\n  2. 添加新用户\n  3. 退出\n请输入选项 (1/2/3): ").strip()

    if choice == "1":
        init_auth_system()
    elif choice == "2":
        init_auth_system()  # 确保系统已初始化
        add_user_interactive()
    elif choice == "3":
        print("退出")
    else:
        print("无效选项")
