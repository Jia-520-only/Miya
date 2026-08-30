"""
弥娅统一权限引擎 (Miya Unified Permission Engine)

v7.0 - 替代碎片化的权限检查系统

设计原则：
1. 单一数据源：config/permissions.json
2. 统一用户ID：platform_userid 格式
3. 集中角色模型：superadmin / admin / moderator / user
4. 可读写：支持 API 和工具修改权限

用法：
    from core.unified_permission import get_permission_engine
    engine = get_permission_engine()
    engine.is_superadmin("qq_1523878699")  # True
    engine.check("qq_1523878699", "tool.web_search")  # True
    engine.check_command("qq_1523878699", "/形态")  # True
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("Miya.PermissionEngine")


class UnifiedPermissionEngine:
    """
    统一权限引擎

    角色层级：
      superadmin  >  admin  >  moderator  >  user
          *.*        *.tool.*  partial.*     default
    """

    ROLE_SUPERADMIN = "superadmin"
    ROLE_ADMIN = "admin"
    ROLE_MODERATOR = "moderator"
    ROLE_USER = "user"

    def __init__(self, config_path: str = "config/permissions.json"):
        self._config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._config_mtime: float = 0
        self._superadmin_ids: Set[str] = set()
        self._reload()

    # ==================== 配置管理 ====================

    def _reload(self):
        """重新加载配置"""
        try:
            if not self._config_path.exists():
                logger.warning(f"权限配置不存在: {self._config_path}")
                self._config = self._default_config()
                return

            mtime = self._config_path.stat().st_mtime
            if mtime == self._config_mtime and self._config:
                return

            self._config = json.loads(self._config_path.read_text("utf-8"))
            self._config_mtime = mtime
            self._rebuild_superadmin_cache()
            logger.debug("权限配置已加载")
        except Exception as e:
            logger.error(f"加载权限配置失败: {e}")
            self._config = self._default_config()

    def _rebuild_superadmin_cache(self):
        """重建超级管理员缓存（自动展开平台前缀）"""
        self._superadmin_ids.clear()
        self._superadmin_map: Dict[str, str] = {}  # platform → raw_id 映射

        # 从新版 superadmins 字段 (v7.0)
        superadmins = self._config.get("superadmins", {})
        for person_key, info in superadmins.items():
            ids = info.get("ids", {})

            # 旧格式兼容：platforms 列表 + 单ID
            if not ids and "platforms" in info:
                raw_id = person_key
                if str(raw_id).isdigit():
                    self._superadmin_ids.add(raw_id)
                    for platform in info.get("platforms", []):
                        self._superadmin_ids.add(f"{platform}_{raw_id}")
                continue

            # 新格式：ids 字典 {platform: [user_ids]}
            for platform, raw_ids in ids.items():
                raw_ids_list = ([raw_ids] if raw_ids else []) if isinstance(raw_ids, str) else raw_ids or []
                for raw_id in raw_ids_list:
                    raw_id = str(raw_id)
                    if not raw_id:
                        continue
                    self._superadmin_ids.add(raw_id)
                    self._superadmin_ids.add(f"{platform}_{raw_id}")
                    self._superadmin_map[platform] = raw_id

        # 从旧版 users 中找 Admin 组成员（兼容）
        for user in self._config.get("users", []):
            groups = user.get("permission_groups", [])
            if "Admin" in groups:
                uid = user.get("user_id", "")
                if uid:
                    self._superadmin_ids.add(uid)

        # 从白名单（兼容）
        whitelist = self._config.get("special_rules", {}).get("super_admin_whitelist", [])
        self._superadmin_ids.update(whitelist)

    def _get_superadmin_id_for_platform(self, platform: str) -> Optional[str]:
        """获取某平台对应的超管原始 ID"""
        return self._superadmin_map.get(platform)

    def reload(self):
        self._reload()

    @staticmethod
    def _default_config() -> Dict:
        return {
            "version": "1.0.0",
            "permission_groups": {},
            "platform_defaults": {},
            "users": [],
            "command_permissions": {"enabled": False, "roles": [], "commands": {}},
            "special_rules": {"super_admin_whitelist": []},
            "security": {},
        }

    # ==================== 超级管理员 ====================

    def is_superadmin(self, user_id: str, platform: str = "") -> bool:
        """
        检查用户是否是超级管理员（支持跨平台匹配）

        匹配策略（按优先级）：
        1. 精确匹配 user_id（含 platform_userid 格式）
        2. 按平台从 superadmins.ids 查找对应原始ID
        3. linked_to 关联匹配
        """
        if not user_id:
            return False
        self._reload()

        # 精确匹配
        if user_id in self._superadmin_ids:
            return True

        # platform_userid 格式
        if platform:
            check_id = f"{platform}_{user_id}"
            if check_id in self._superadmin_ids:
                return True

        # 从 superadmins 按平台查找
        superadmins = self._config.get("superadmins", {})
        for person_key, info in superadmins.items():
            ids = info.get("ids", {})

            # 新格式：ids[platform] 匹配（支持字符串和数组）
            if ids:
                expected = ids.get(platform, [])
                if isinstance(expected, str):
                    expected = [expected] if expected else []
                if str(user_id) in [str(x) for x in expected]:
                    return True

            # 旧格式兼容：platforms 列表
            platforms = info.get("platforms", [])
            if platforms and str(user_id) == person_key:
                return True

        # 从 users 的 linked_to 检查
        for user in self._config.get("users", []):
            linked = user.get("linked_to", "")
            if linked and linked == user_id:
                return True

        return False

    def is_superadmin_cross_platform(self, platform: str, raw_user_id: str) -> bool:
        """跨平台超管检查 — 简化调用"""
        return self.is_superadmin(raw_user_id, platform=platform)

    def set_superadmin(self, user_id: str, platform: str = "", username: str = ""):
        """设置超级管理员（持久化到配置文件）"""
        self._reload()
        self._superadmin_ids.add(user_id)
        self._add_or_update_user(user_id, platform, username, ["Admin", "Developer"])
        self._save_config(silent=True)

    def get_superadmin_ids(self) -> Set[str]:
        self._reload()
        return self._superadmin_ids.copy()

    # ==================== 权限检查 ====================

    def check(self, user_id: str, permission: str, context: Optional[Dict] = None) -> bool:
        """
        检查用户是否有指定权限

        Args:
            user_id: 用户ID (平台_原始ID)
            permission: 权限节点 (如 tool.web_search)
            context: 上下文 (含 platform 等)
        """
        if not user_id:
            return False

        self._reload()

        # Superadmin 拥有所有权限
        if self.is_superadmin(user_id):
            return True

        permissions = self._get_user_permissions(user_id, context)
        return self._match_permission(permissions, permission)

    def check_command(self, user_id: str, command: str, platform: str = "") -> bool:
        """检查用户是否有执行某命令的权限"""
        if not user_id or not command:
            return False

        self._reload()

        if self.is_superadmin(user_id):
            return True

        cmd_config = self._config.get("command_permissions", {})
        if not cmd_config.get("enabled", False):
            return True

        cmd = command.strip().lower()

        # 支持 /command 或 command 两种格式
        commands = cmd_config.get("commands", {})

        # 精确匹配 + / 前缀匹配
        cmd_stripped = cmd.lstrip("/")
        for cmd_key, _cmd_info in commands.items():
            key_stripped = cmd_key.lower().lstrip("/")
            if cmd_stripped == key_stripped:
                return False  # 非 superadmin 拒绝执行受保护命令

        return True  # 非受保护命令放行

    def get_role_level(self, user_id: str) -> str:
        """获取用户角色等级"""
        if not user_id:
            return self.ROLE_USER
        self._reload()
        if self.is_superadmin(user_id):
            return self.ROLE_SUPERADMIN
        return self.ROLE_USER

    # ==================== 内部方法 ====================

    def _get_user_permissions(self, user_id: str, context: Optional[Dict] = None) -> List[str]:
        """获取用户的所有权限节点"""
        config = self._config
        permissions: List[str] = []

        # 查找用户
        user = self._find_user(user_id)
        platform = (context or {}).get("platform", "")

        if user:
            groups = user.get("permission_groups", [])
        else:
            # 新用户，使用平台默认权限
            groups = config.get("platform_defaults", {}).get(platform, ["Default"])

        # 收集权限
        perm_groups = config.get("permission_groups", {})
        for group_name in groups:
            group = perm_groups.get(group_name, {})
            perms = group.get("permissions", [])
            if isinstance(perms, list):
                permissions.extend(perms)

        return permissions

    def _find_user(self, user_id: str) -> Optional[Dict]:
        """查找用户"""
        for user in self._config.get("users", []):
            if user.get("user_id") == user_id:
                return user

            # 检查 linked_to
            linked = user.get("linked_to", "")
            if linked and linked == user_id:
                return user

        return None

    def _add_or_update_user(self, user_id: str, platform: str, username: str, groups: List[str]):
        """添加或更新用户配置"""
        config = self._config
        user = self._find_user(user_id)

        if user:
            existing_groups = user.get("permission_groups", [])
            new_groups = list(set(existing_groups + groups))
            user["permission_groups"] = new_groups
        else:
            config.setdefault("users", []).append(
                {
                    "user_id": user_id,
                    "username": username or user_id,
                    "platform": platform,
                    "permission_groups": groups,
                    "description": "通过 API 添加",
                }
            )

        self._rebuild_superadmin_cache()

    @staticmethod
    def _match_permission(perm_list: List[str], permission: str) -> bool:
        """通配符权限匹配"""
        for perm in perm_list:
            if perm == "*.*":
                return True
            if perm == permission:
                return True
            if "." not in perm and "." in permission:
                # category.* 匹配 category.xxx
                if perm.endswith(".*") and permission.startswith(perm[:-2]):
                    return True
            parts, check_parts = perm.split("."), permission.split(".")
            if len(parts) <= len(check_parts):
                match = True
                for i, p in enumerate(parts):
                    if p != "*" and p != (check_parts[i] if i < len(check_parts) else ""):
                        match = False
                        break
                if match:
                    return True
        return False

    # ==================== 用户管理 ====================

    def get_user_groups(self, user_id: str) -> List[str]:
        """获取用户所属权限组"""
        user = self._find_user(user_id)
        if user:
            return user.get("permission_groups", [])
        return []

    def get_user_permissions_list(self, user_id: str, context: Optional[Dict] = None) -> List[str]:
        """获取用户所有权限（展开）"""
        self._reload()
        return self._get_user_permissions(user_id, context)

    def grant_role(self, user_id: str, platform: str, username: str, groups: List[str]) -> bool:
        """授予用户权限组（持久化）"""
        self._reload()
        self._add_or_update_user(user_id, platform, username, groups)
        return self._save_config()

    def revoke_role(self, user_id: str, groups: Optional[List[str]] = None) -> bool:
        """撤销用户权限组"""
        self._reload()
        config = self._config
        users = config.get("users", [])
        for user in users:
            if user.get("user_id") == user_id:
                if groups:
                    user["permission_groups"] = [g for g in user.get("permission_groups", []) if g not in groups]
                else:
                    user["permission_groups"] = ["Default"]
                self._rebuild_superadmin_cache()
                return self._save_config()
        return False

    def list_users(self) -> List[Dict]:
        self._reload()
        return deepcopy(self._config.get("users", []))

    def list_roles(self) -> Dict:
        self._reload()
        return deepcopy(self._config.get("permission_groups", {}))

    def get_stats(self) -> Dict:
        self._reload()
        return {
            "superadmin_count": len(self._superadmin_ids),
            "user_count": len(self._config.get("users", [])),
            "role_count": len(self._config.get("permission_groups", {})),
            "config_file": str(self._config_path),
            "version": self._config.get("version"),
        }

    # ==================== 持久化 ====================

    def _save_config(self, silent: bool = False) -> bool:
        """保存配置到文件"""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            json_text = json.dumps(self._config, ensure_ascii=False, indent=2)
            self._config_path.write_text(json_text, "utf-8")
            self._config_mtime = self._config_path.stat().st_mtime
            if not silent:
                logger.info("权限配置已保存")
            return True
        except Exception as e:
            logger.error(f"保存权限配置失败: {e}")
            return False


# ==================== 全局单例 ====================

_global_engine: Optional[UnifiedPermissionEngine] = None


def get_permission_engine() -> UnifiedPermissionEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = UnifiedPermissionEngine()
    return _global_engine
