"""
迁移脚本：将旧的权限配置迁移到统一配置文件

将 data/auth/users.json 和 data/auth/groups.json 迁移到 config/permissions.json
"""

import json
from pathlib import Path
from datetime import datetime


def migrate_old_to_unified():
    """将旧配置迁移到统一配置"""

    print("=" * 60)
    print("弥娅权限配置迁移工具")
    print("=" * 60)
    print()

    # 旧配置文件路径
    old_users_file = Path("data/auth/users.json")
    old_groups_file = Path("data/auth/groups.json")

    # 新配置文件路径
    new_config_file = Path("config/permissions.json")

    # 检查旧配置是否存在
    if not old_users_file.exists():
        print("[!] 旧配置文件不存在: data/auth/users.json")
        print("    将使用默认配置。")
        old_users = {"users": []}
    else:
        # 备份旧配置
        backup_file = Path(f"data/auth/users.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        backup_file.write_text(old_users_file.read_text(encoding='utf-8'), encoding='utf-8')
        print(f"[√] 已备份旧用户配置: {backup_file}")

        old_users = json.loads(old_users_file.read_text(encoding='utf-8'))
        print(f"[√] 读取到 {len(old_users.get('users', []))} 个用户")

    if not old_groups_file.exists():
        print("[!] 旧配置文件不存在: data/auth/groups.json")
        print("    将使用默认配置。")
        old_groups = {"groups": {}}
    else:
        # 备份旧配置
        backup_file = Path(f"data/auth/groups.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        backup_file.write_text(old_groups_file.read_text(encoding='utf-8'), encoding='utf-8')
        print(f"[√] 已备份旧权限组配置: {backup_file}")

        old_groups = json.loads(old_groups_file.read_text(encoding='utf-8'))
        print(f"[√] 读取到 {len(old_groups.get('groups', {}))} 个权限组")

    print()

    # 创建统一配置
    unified_config = {
        "version": "1.0.0",
        "last_updated": datetime.now().isoformat(),
        "description": "弥娅系统统一权限配置文件",
        "permission_groups": {},
        "platform_defaults": {
            "terminal": ["Terminal"],
            "web": ["Web"],
            "desktop": ["Desktop"],
            "qq": ["QQ"],
            "discord": ["Default"],
            "telegram": ["Default"]
        },
        "users": [],
        "special_rules": {
            "admin_whitelist": ["terminal_default"],
            "super_admin_whitelist": ["terminal_default"]
        },
        "disabled_permissions": [],
        "platform_restrictions": {
            "terminal": {
                "allowed_groups": [],
                "forbidden_groups": []
            },
            "web": {
                "allowed_groups": [],
                "forbidden_groups": ["Terminal"]
            },
            "desktop": {
                "allowed_groups": [],
                "forbidden_groups": []
            },
            "qq": {
                "allowed_groups": ["Default", "QQ", "Web", "Admin"],
                "forbidden_groups": ["Terminal", "Developer"]
            }
        },
        "security": {
            "enable_audit": True,
            "enable_cache": True,
            "cache_ttl": 300,
            "log_denied": True,
            "log_allowed": False,
            "whitelist_mode": False,
            "user_whitelist": []
        }
    }

    # 迁移权限组
    print("迁移权限组...")
    old_permission_groups = old_groups.get("groups", {})

    # 默认权限组（如果旧配置中没有）
    default_groups = {
        "Default": {
            "name": "默认权限组",
            "description": "所有用户默认拥有的基本权限",
            "permissions": [
                "tool.get_current_time",
                "memory.read",
                "knowledge.search",
                "agent.chat"
            ]
        },
        "Admin": {
            "name": "管理员",
            "description": "拥有系统的所有权限",
            "permissions": ["*.*"]
        },
        "Terminal": {
            "name": "终端用户",
            "description": "终端平台用户的基础权限",
            "permissions": [
                "tool.terminal.execute",
                "tool.web_search",
                "tool.get_current_time",
                "memory.read",
                "memory.write",
                "knowledge.search",
                "agent.chat"
            ]
        },
        "Web": {
            "name": "Web用户",
            "description": "Web平台用户的基础权限",
            "permissions": [
                "tool.web_search",
                "tool.get_current_time",
                "memory.read",
                "memory.write",
                "knowledge.search",
                "agent.chat"
            ]
        },
        "Desktop": {
            "name": "Desktop用户",
            "description": "Desktop平台用户的基础权限",
            "permissions": [
                "tool.web_search",
                "tool.get_current_time",
                "memory.read",
                "memory.write",
                "knowledge.search",
                "agent.chat",
                "system.config.read"
            ]
        },
        "QQ": {
            "name": "QQ用户",
            "description": "QQ平台用户的基础权限",
            "permissions": [
                "tool.web_search",
                "tool.get_current_time",
                "memory.read",
                "knowledge.search",
                "agent.chat"
            ]
        },
        "Developer": {
            "name": "开发者",
            "description": "开发者权限，可访问调试和系统信息",
            "permissions": [
                "tool.*",
                "memory.*",
                "knowledge.*",
                "agent.*",
                "system.*",
                "config.*"
            ]
        }
    }

    # 合并权限组（优先使用旧配置）
    unified_config["permission_groups"] = {**default_groups, **old_permission_groups}

    print(f"  [√] 迁移了 {len(unified_config['permission_groups'])} 个权限组")
    for group_name in unified_config["permission_groups"]:
        group = unified_config["permission_groups"][group_name]
        print(f"      - {group_name}: {group.get('name', group_name)}")

    # 迁移用户
    print()
    print("迁移用户...")
    old_users_list = old_users.get("users", [])

    for old_user in old_users_list:
        user_id = old_user.get("user_id")
        username = old_user.get("username", user_id)
        platform = old_user.get("platform", "unknown")
        permission_groups = old_user.get("permission_groups", ["Default"])
        description = old_user.get("description", "")
        created_at = old_user.get("created_at", datetime.now().isoformat())

        new_user = {
            "user_id": user_id,
            "username": username,
            "platform": platform,
            "permission_groups": permission_groups,
            "description": description,
            "created_at": created_at
        }

        unified_config["users"].append(new_user)
        print(f"  [√] 迁移用户: {user_id} ({username}) - 平台: {platform}, 组: {permission_groups}")

    # 如果没有用户，添加默认用户
    if not unified_config["users"]:
        print()
        print("  [!] 没有找到用户，添加默认用户...")
        unified_config["users"] = [
            {
                "user_id": "terminal_default",
                "username": "默认终端用户",
                "platform": "terminal",
                "permission_groups": ["Admin"],
                "description": "终端平台的默认管理员用户",
                "created_at": "2026-03-11T00:00:00"
            },
            {
                "user_id": "web_default",
                "username": "默认Web用户",
                "platform": "web",
                "permission_groups": ["Web"],
                "description": "Web平台的默认用户",
                "created_at": "2026-03-11T00:00:00"
            },
            {
                "user_id": "desktop_default",
                "username": "默认Desktop用户",
                "platform": "desktop",
                "permission_groups": ["Desktop"],
                "description": "Desktop平台的默认用户",
                "created_at": "2026-03-11T00:00:00"
            }
        ]
        print("  [√] 添加了 3 个默认用户")

    print()

    # 保存新配置
    print("保存统一配置文件...")
    new_config_file.parent.mkdir(parents=True, exist_ok=True)

    # 如果配置文件已存在，备份
    if new_config_file.exists():
        backup_file = Path(f"config/permissions.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        backup_file.write_text(new_config_file.read_text(encoding='utf-8'), encoding='utf-8')
        print(f"[√] 已备份现有配置: {backup_file}")

    # 保存新配置
    new_config_file.write_text(
        json.dumps(unified_config, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )

    print(f"[√] 已保存统一配置: {new_config_file}")

    print()
    print("=" * 60)
    print("迁移完成！")
    print("=" * 60)
    print()
    print("下一步：")
    print("  1. 检查配置文件: config/permissions.json")
    print("  2. 根据需要修改配置")
    print("  3. 重启弥娅系统")
    print()
    print("注意事项：")
    print("  - 旧配置文件已备份")
    print("  - 权限只能通过配置文件修改，不支持通过命令修改")
    print("  - 修改配置后需要重启系统才能生效")
    print()


if __name__ == "__main__":
    try:
        migrate_old_to_unified()
    except Exception as e:
        print(f"\n[!] 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        print("\n请手动配置 config/permissions.json 文件。")
