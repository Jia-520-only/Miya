"""
权限核心逻辑 - 提取自QQ机器人鉴权系统

功能：
- 权限检查 (ckPerm)
- 权限计算
- 权限匹配规则
- 审计日志记录
- 权限缓存支持
- 支持统一配置文件模式
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)


class PermissionCore:
    """权限核心管理器"""

    def __init__(
        self,
        enable_audit: bool = True,
        enable_cache: bool = True,
        use_unified_config: bool = True
    ):
        """
        初始化权限核心

        Args:
            enable_audit: 是否启用审计日志
            enable_cache: 是否启用缓存
            use_unified_config: 是否使用统一配置文件（推荐）
        """
        self.use_unified_config = use_unified_config

        # 如果使用统一配置，则初始化统一权限管理器
        if use_unified_config:
            try:
                from .unified_permission_manager import UnifiedPermissionManager
                self._unified_manager = UnifiedPermissionManager()
                logger.info("使用统一权限配置文件模式")
            except Exception as e:
                logger.warning(f"加载统一权限管理器失败: {e}，回退到传统模式")
                self.use_unified_config = False
                self._unified_manager = None
        else:
            self._unified_manager = None

        # 传统模式的文件路径
        self.users_file = Path("data/auth/users.json")
        self.groups_file = Path("data/auth/groups.json")

        # 审计日志
        self.enable_audit = enable_audit
        self._audit_logger = None

        # 权限缓存
        self.enable_cache = enable_cache
        self._cache = None
    
    def load_users(self) -> Dict[str, Any]:
        """加载用户数据"""
        if self.users_file.exists():
            return json.loads(self.users_file.read_text(encoding='utf-8', errors='replace'))
        return {"users": []}

    def load_groups(self) -> Dict[str, Any]:
        """加载权限组数据"""
        if self.groups_file.exists():
            return json.loads(self.groups_file.read_text(encoding='utf-8', errors='replace'))
        return {"groups": {}}
    
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
        检查权限

        Args:
            user_id: 用户ID (格式: platform_id, 如: qq_123, web_user456)
            permission: 权限节点 (如: tool.web_search, agent.task.execute)
            context: 上下文信息 (如: platform, group_id, channel_id)
            list_mode: 是否返回所有权限列表（True返回权限详情，False返回是否有权限）
            log_audit: 是否记录审计日志
            use_cache: 是否使用缓存

        Returns:
            list_mode=True: 返回权限详情字符串
            list_mode=False: 返回是否有权限 (True/False)
        """
        # 如果使用统一配置，委托给统一权限管理器
        if self.use_unified_config and self._unified_manager:
            return self._unified_manager.check_permission(
                user_id=user_id,
                permission=permission,
                context=context,
                list_mode=list_mode,
                log_audit=log_audit,
                use_cache=use_cache
            )

        # 【传统模式】检查缓存
        if use_cache and self.enable_cache and not list_mode:
            cached_result = self._get_from_cache(user_id, permission)
            if cached_result is not None:
                return cached_result

        perm_list = []
        perm_groups = ["Default"]  # 默认权限组

        # 加载数据
        users_data = self.load_users()
        groups_data = self.load_groups()

        # 查找用户
        user = None
        for u in users_data.get("users", []):
            if u.get("user_id") == user_id:
                user = u
                break
        
        if not user:
            # 用户不存在，只能使用默认权限组
            user = {
                "user_id": user_id,
                "permission_groups": ["Default"],
                "permissions": []
            }
        
        # 收集用户权限组
        user_groups = user.get("permission_groups", [])
        perm_groups.extend(user_groups)
        
        # 收集用户直接权限
        user_perms = user.get("permissions", [])
        if isinstance(user_perms, str):
            # 如果是字符串（如"*"），转为列表
            perm_list.append(user_perms)
        elif isinstance(user_perms, list):
            perm_list.extend(user_perms)
        
        # 从权限组收集权限
        groups = groups_data.get("groups", {})
        for group_name in perm_groups:
            group = groups.get(group_name, {})
            group_perms = group.get("permissions", [])
            if isinstance(group_perms, list):
                perm_list.extend(group_perms)
            elif isinstance(group_perms, str):
                perm_list.append(group_perms)
        
        # 如果是list_mode，返回所有权限
        if list_mode:
            return f"权限组: {set(perm_groups)}, 拥有权限: {set(perm_list)}"

        # 检查权限
        result = self._has_permission(perm_list, permission)

        # 【新增】审计日志
        if log_audit and self.enable_audit:
            try:
                self._get_audit_logger().log_permission_check(
                    user_id=user_id,
                    permission=permission,
                    result=result,
                    platform=context.get('platform') if context else None
                )
            except Exception as e:
                pass  # 审计日志失败不应影响主流程

        # 【新增】缓存结果
        if use_cache and self.enable_cache and not list_mode:
            self._save_to_cache(user_id, permission, result)

        return result

    def _get_audit_logger(self):
        """获取审计日志器"""
        if self._audit_logger is None:
            try:
                from .audit import get_audit_logger
                self._audit_logger = get_audit_logger()
            except Exception:
                pass
        return self._audit_logger

    def _get_cache(self):
        """获取缓存实例"""
        if self._cache is None:
            try:
                from .cache import get_permission_cache
                self._cache = get_permission_cache()
            except Exception:
                pass
        return self._cache

    def _get_from_cache(self, user_id: str, permission: str) -> Optional[bool]:
        """从缓存获取"""
        cache = self._get_cache()
        if cache:
            return cache.get(user_id, permission)
        return None

    def _save_to_cache(self, user_id: str, permission: str, result: bool):
        """保存到缓存"""
        cache = self._get_cache()
        if cache:
            cache.set(user_id, permission, result)

    def invalidate_cache(self, user_id: Optional[str] = None):
        """失效缓存"""
        cache = self._get_cache()
        if cache:
            if user_id:
                cache.invalidate_user(user_id)
            else:
                cache.clear_all()

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        cache = self._get_cache()
        if cache:
            return cache.get_stats()
        return {"enabled": False}

    def _has_permission(self, perm_list: List[str], permission: str) -> bool:
        """
        检查权限列表中是否有指定权限
        
        权限规则（优先级从高到低）：
        1. 超级管理员 ("*") - 最高优先级
        2. 精确拒绝 (例如: -tool.web_search)
        3. 精确允许 (例如: tool.web_search)
        4. 父级权限 (例如: tool.* 匹配 tool.web_search)
        5. 默认拒绝
        """
        # 1. 超级管理员
        if "*" in perm_list:
            return True
        
        # 2. 精确拒绝
        if f"-{permission}" in perm_list:
            return False
        
        # 3. 精确允许
        if permission in perm_list:
            return True
        
        # 4. 父级权限处理
        if "." in permission:
            parts = permission.split(".")
            parent_module = parts[0]
            
            # 4.1 父级显式拒绝
            if f"-{parent_module}" in perm_list or f"-{parent_module}.*" in perm_list:
                return False
            
            # 4.2 父级通配符允许
            if f"{parent_module}.*" in perm_list or parent_module in perm_list:
                return True
        
        # 5. 默认拒绝
        return False
    
    def grant_permission(self, user_id: str, permission: str) -> bool:
        """
        授予权限
        
        Args:
            user_id: 用户ID
            permission: 权限节点
        
        Returns:
            是否成功
        """
        users_data = self.load_users()
        
        # 查找或创建用户
        user = None
        for u in users_data.get("users", []):
            if u.get("user_id") == user_id:
                user = u
                break
        
        if not user:
            user = {
                "user_id": user_id,
                "username": user_id,
                "platform": "unknown",
                "permission_groups": ["Default"],
                "permissions": [],
                "created_at": datetime.now().isoformat()
            }
            users_data["users"].append(user)
        
        # 确保permissions是列表
        if "permissions" not in user:
            user["permissions"] = []
        elif isinstance(user["permissions"], str):
            # 如果是字符串，转为列表
            user["permissions"] = [user["permissions"]] if user["permissions"] else []
        
        # 添加权限
        if isinstance(user["permissions"], list):
            if permission not in user["permissions"]:
                user["permissions"].append(permission)
        
        # 保存
        self.users_file.write_text(
            json.dumps(users_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        return True
    
    def revoke_permission(self, user_id: str, permission: str) -> bool:
        """
        撤销权限
        
        Args:
            user_id: 用户ID
            permission: 权限节点
        
        Returns:
            是否成功
        """
        users_data = self.load_users()
        
        # 查找用户
        user = None
        for u in users_data.get("users", []):
            if u.get("user_id") == user_id:
                user = u
                break
        
        if not user:
            return False
        
        # 移除权限
        user_perms = user.get("permissions", [])
        if isinstance(user_perms, list):
            if permission in user_perms:
                user_perms.remove(permission)
                user["permissions"] = user_perms
        
        # 保存
        self.users_file.write_text(
            json.dumps(users_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        
        return True
    
    def list_user_permissions(self, user_id: str) -> Dict[str, Any]:
        """
        列出用户权限详情
        
        Args:
            user_id: 用户ID
        
        Returns:
            用户权限详情
        """
        users_data = self.load_users()
        groups_data = self.load_groups()
        
        # 查找用户
        user = None
        for u in users_data.get("users", []):
            if u.get("user_id") == user_id:
                user = u
                break
        
        if not user:
            return {"error": "用户不存在"}
        
        # 计算权限
        perm_list = []
        perm_groups = user.get("permission_groups", [])
        
        # 用户直接权限
        user_perms = user.get("permissions", [])
        if isinstance(user_perms, list):
            perm_list.extend(user_perms)
        elif isinstance(user_perms, str):
            perm_list.append(user_perms)
        
        # 权限组权限
        groups = groups_data.get("groups", {})
        for group_name in perm_groups:
            group = groups.get(group_name, {})
            group_perms = group.get("permissions", [])
            if isinstance(group_perms, list):
                perm_list.extend(group_perms)
            elif isinstance(group_perms, str):
                perm_list.append(group_perms)
        
        return {
            "user_id": user_id,
            "username": user.get("username", user_id),
            "permission_groups": perm_groups,
            "direct_permissions": user_perms if isinstance(user_perms, list) else [user_perms],
            "effective_permissions": list(set(perm_list)),
            "platform": user.get("platform", "unknown"),
            "created_at": user.get("created_at")
        }
    
    def save_users(self, users_data: Dict[str, Any]):
        """保存用户数据"""
        self.users_file.write_text(
            json.dumps(users_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
    
    def save_groups(self, groups_data: Dict[str, Any]):
        """保存权限组数据"""
        self.groups_file.write_text(
            json.dumps(groups_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

