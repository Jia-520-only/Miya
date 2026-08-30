"""
统一权限管理器 - 从单一配置文件读取所有权限

特性：
- 从 config/permissions.json 或 config/permissions.yaml 读取配置
- 不支持通过命令修改权限，只能通过配置文件
- 支持多平台统一管理
- 支持权限缓存和审计
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class UnifiedPermissionManager:
    """统一权限管理器"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化权限管理器

        Args:
            config_path: 配置文件路径（可选，默认为 config/permissions.json）
        """
        # 配置文件路径
        if config_path is None:
            self.config_file = Path("config/permissions.json")
            # 如果JSON不存在，尝试YAML
            if not self.config_file.exists():
                yaml_file = Path("config/permissions.yaml")
                if yaml_file.exists():
                    self.config_file = yaml_file
        else:
            self.config_file = Path(config_path)

        # 权限缓存
        self._cache = {}
        self._config_cache = None
        self._config_mtime = None

        # 安全设置
        self._read_only = True  # 只读模式，不允许通过代码修改权限

        logger.info(f"统一权限管理器初始化完成，配置文件: {self.config_file}")

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        # 检查文件是否被修改
        current_mtime = self.config_file.stat().st_mtime if self.config_file.exists() else None

        # 如果缓存有效且文件未被修改，使用缓存
        if self._config_cache and self._config_mtime == current_mtime:
            return self._config_cache

        # 重新加载配置
        if not self.config_file.exists():
            logger.error(f"权限配置文件不存在: {self.config_file}")
            return self._get_default_config()

        try:
            content = self.config_file.read_text(encoding='utf-8')

            if self.config_file.suffix == '.yaml' or self.config_file.suffix == '.yml':
                # 尝试导入 PyYAML
                try:
                    import yaml
                    config = yaml.safe_load(content)
                except ImportError:
                    logger.warning("PyYAML未安装，无法解析YAML配置文件")
                    logger.warning("请安装 PyYAML: pip install pyyaml")
                    config = self._get_default_config()
            else:
                # JSON 格式
                config = json.loads(content)

            # 更新缓存
            self._config_cache = config
            self._config_mtime = current_mtime

            logger.info(f"成功加载权限配置: {config.get('version', 'unknown')}")
            return config

        except Exception as e:
            logger.error(f"加载权限配置文件失败: {e}", exc_info=True)
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "version": "1.0.0",
            "permission_groups": {
                "Default": {
                    "name": "默认权限组",
                    "permissions": ["tool.get_current_time", "memory.read"]
                },
                "Admin": {
                    "name": "管理员",
                    "permissions": ["*.*"]
                }
            },
            "platform_defaults": {
                "terminal": ["Default"],
                "web": ["Default"]
            },
            "users": [
                {
                    "user_id": "terminal_default",
                    "platform": "terminal",
                    "permission_groups": ["Admin"]
                }
            ],
            "special_rules": {
                "admin_whitelist": [],
                "super_admin_whitelist": []
            },
            "disabled_permissions": [],
            "platform_restrictions": {},
            "security": {
                "enable_audit": True,
                "enable_cache": True,
                "cache_ttl": 300
            }
        }

    def check_permission(
        self,
        user_id: str,
        permission: str,
        context: Optional[Dict[str, Any]] = None,
        list_mode: bool = False,
        log_audit: bool = True,
        use_cache: bool = True
    ) -> Union[str, bool]:
        """
        检查用户是否有指定权限

        Args:
            user_id: 用户ID（格式: platform_id）
            permission: 权限节点（如: tool.web_search）
            context: 上下文信息（如: platform）
            list_mode: 是否返回权限详情
            log_audit: 是否记录审计日志
            use_cache: 是否使用缓存

        Returns:
            list_mode=True: 返回权限详情字符串
            list_mode=False: 返回是否有权限（True/False）
        """
        # 检查缓存
        cache_key = f"{user_id}:{permission}"
        if use_cache and not list_mode and cache_key in self._cache:
            cached_result, cache_time = self._cache[cache_key]
            # 检查缓存是否过期
            config = self._load_config()
            ttl = config.get("security", {}).get("cache_ttl", 300)
            if (datetime.now().timestamp() - cache_time) < ttl:
                return cached_result

        # 加载配置
        config = self._load_config()

        # 获取安全设置
        security = config.get("security", {})
        enable_audit = security.get("enable_audit", True)
        enable_cache = security.get("enable_cache", True)

        # 收集用户的所有权限
        perm_list = self._get_user_permissions(user_id, config, context)

        # 检查权限
        result = self._has_permission(perm_list, permission, config)

        # 记录审计日志
        if log_audit and enable_audit:
            self._log_permission_check(user_id, permission, result, context)

        # 缓存结果
        if use_cache and enable_cache and not list_mode:
            self._cache[cache_key] = (result, datetime.now().timestamp())

        # 返回结果
        if list_mode:
            return f"拥有权限: {set(perm_list)}"
        return result

    def _get_user_permissions(
        self,
        user_id: str,
        config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        获取用户的所有权限

        Args:
            user_id: 用户ID
            config: 配置数据
            context: 上下文信息

        Returns:
            权限列表
        """
        perm_list = []
        platform = context.get('platform') if context else None

        # 特殊规则：检查白名单
        special_rules = config.get("special_rules", {})
        admin_whitelist = special_rules.get("admin_whitelist", [])
        super_admin_whitelist = special_rules.get("super_admin_whitelist", [])

        # 超级管理员拥有所有权限
        if user_id in super_admin_whitelist:
            return ["*.*"]

        # 管理员白名单也拥有所有权限
        if user_id in admin_whitelist:
            return ["*.*"]

        # 查找用户配置
        users = config.get("users", [])
        user = None
        for u in users:
            if u.get("user_id") == user_id:
                user = u
                break

        # 如果用户不存在，使用平台默认权限
        if user is None:
            if platform:
                platform_defaults = config.get("platform_defaults", {})
                default_groups = platform_defaults.get(platform, ["Default"])
            else:
                default_groups = ["Default"]
            user = {
                "user_id": user_id,
                "platform": platform or "unknown",
                "permission_groups": default_groups
            }

        # 检查平台限制
        user_platform = user.get("platform", platform or "unknown")
        platform_restrictions = config.get("platform_restrictions", {})
        restrictions = platform_restrictions.get(user_platform, {})

        # 收集用户权限组
        user_groups = user.get("permission_groups", [])

        # 应用平台限制
        forbidden_groups = restrictions.get("forbidden_groups", [])
        allowed_groups = restrictions.get("allowed_groups", [])

        final_groups = []
        for group in user_groups:
            # 如果有限制，检查是否在允许列表中
            if allowed_groups and group not in allowed_groups:
                continue
            # 检查是否在禁止列表中
            if group in forbidden_groups:
                continue
            final_groups.append(group)

        # 从权限组收集权限
        permission_groups = config.get("permission_groups", {})
        for group_name in final_groups:
            group = permission_groups.get(group_name, {})
            group_perms = group.get("permissions", [])
            if isinstance(group_perms, list):
                perm_list.extend(group_perms)
            elif isinstance(group_perms, str):
                perm_list.append(group_perms)

        return perm_list

    def _has_permission(
        self,
        perm_list: List[str],
        permission: str,
        config: Dict[str, Any]
    ) -> bool:
        """
        检查权限列表中是否有指定权限

        Args:
            perm_list: 权限列表
            permission: 要检查的权限
            config: 配置数据

        Returns:
            是否有权限
        """
        # 检查禁用的权限
        disabled_perms = config.get("disabled_permissions", [])
        for disabled in disabled_perms:
            if self._match_permission(disabled, permission):
                return False

        # 检查权限列表
        for perm in perm_list:
            if perm == "*.*":
                return True

            # 匹配通配符
            if self._match_permission(perm, permission):
                return True

        return False

    def _match_permission(self, pattern: str, permission: str) -> bool:
        """
        匹配权限模式

        Args:
            pattern: 权限模式（可能包含通配符）
            permission: 要检查的权限

        Returns:
            是否匹配
        """
        # 完全匹配
        if pattern == permission:
            return True

        # 通配符匹配
        if pattern == "*.*":
            return True

        # 分割权限部分
        pattern_parts = pattern.split(".")
        perm_parts = permission.split(".")

        # 检查每一部分
        for i, (p_part, perm_part) in enumerate(zip(pattern_parts, perm_parts)):
            if p_part == "*":
                continue
            if p_part != perm_part:
                return False

        # 如果模式部分更少且最后一个部分是*，则匹配
        if len(pattern_parts) < len(perm_parts):
            last_part = pattern_parts[-1]
            if last_part == "*":
                return True

        return False

    def _log_permission_check(
        self,
        user_id: str,
        permission: str,
        result: bool,
        context: Optional[Dict[str, Any]] = None
    ):
        """记录权限检查日志"""
        security = self._load_config().get("security", {})
        log_denied = security.get("log_denied", True)
        log_allowed = security.get("log_allowed", False)

        if (result and not log_allowed) or (not result and not log_denied):
            return

        level = logger.warning if not result else logger.info
        platform = context.get('platform', 'unknown') if context else 'unknown'

        level(
            f"权限检查 - 用户: {user_id}, 平台: {platform}, "
            f"权限: {permission}, 结果: {'通过' if result else '拒绝'}"
        )

    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户信息

        Args:
            user_id: 用户ID

        Returns:
            用户信息字典，如果用户不存在返回None
        """
        config = self._load_config()
        users = config.get("users", [])

        for user in users:
            if user.get("user_id") == user_id:
                return user.copy()

        return None

    def list_users(self) -> List[Dict[str, Any]]:
        """
        列出所有用户

        Returns:
            用户列表
        """
        config = self._load_config()
        return config.get("users", []).copy()

    def list_permission_groups(self) -> Dict[str, Dict[str, Any]]:
        """
        列出所有权限组

        Returns:
            权限组字典
        """
        config = self._load_config()
        return config.get("permission_groups", {}).copy()

    def get_user_permissions_list(self, user_id: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        获取用户的所有权限列表

        Args:
            user_id: 用户ID
            context: 上下文信息

        Returns:
            权限列表
        """
        config = self._load_config()
        return self._get_user_permissions(user_id, config, context)

    def reload_config(self):
        """重新加载配置文件"""
        # 清除缓存
        self._config_cache = None
        self._config_mtime = None
        self._cache.clear()

        # 重新加载
        self._load_config()

        logger.info("权限配置已重新加载")

    def get_config_info(self) -> Dict[str, Any]:
        """
        获取配置信息

        Returns:
            配置信息
        """
        config = self._load_config()

        return {
            "version": config.get("version"),
            "last_updated": config.get("last_updated"),
            "description": config.get("description"),
            "users_count": len(config.get("users", [])),
            "groups_count": len(config.get("permission_groups", {})),
            "config_file": str(self.config_file),
            "config_exists": self.config_file.exists(),
            "read_only": self._read_only
        }

    # 明确禁止的修改方法
    def add_user(self, **kwargs):
        """添加用户（已禁用 - 只能通过配置文件）"""
        raise NotImplementedError(
            "权限只能通过配置文件修改，不支持通过命令添加用户。"
            "请编辑 config/permissions.json 或 config/permissions.yaml 文件。"
        )

    def remove_user(self, **kwargs):
        """删除用户（已禁用 - 只能通过配置文件）"""
        raise NotImplementedError(
            "权限只能通过配置文件修改，不支持通过命令删除用户。"
            "请编辑 config/permissions.json 或 config/permissions.yaml 文件。"
        )

    def update_user(self, **kwargs):
        """更新用户（已禁用 - 只能通过配置文件）"""
        raise NotImplementedError(
            "权限只能通过配置文件修改，不支持通过命令更新用户。"
            "请编辑 config/permissions.json 或 config/permissions.yaml 文件。"
        )

    def add_permission_group(self, **kwargs):
        """添加权限组（已禁用 - 只能通过配置文件）"""
        raise NotImplementedError(
            "权限只能通过配置文件修改，不支持通过命令添加权限组。"
            "请编辑 config/permissions.json 或 config/permissions.yaml 文件。"
        )

    def update_permission_group(self, **kwargs):
        """更新权限组（已禁用 - 只能通过配置文件）"""
        raise NotImplementedError(
            "权限只能通过配置文件修改，不支持通过命令更新权限组。"
            "请编辑 config/permissions.json 或 config/permissions.yaml 文件。"
        )
