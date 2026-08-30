"""
AuthNet - 鉴权子网
提供统一的用户身份管理和权限检查
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from webnet.subnet_base import BaseSubnet, SubnetConfig

logger = logging.getLogger(__name__)


class AuthSubnet(BaseSubnet):
    """鉴权子网 - 统一用户身份管理和权限检查"""

    def __init__(self, config: Optional[SubnetConfig] = None):
        """初始化鉴权子网"""
        super().__init__(config)
        self.user_mapper = None  # UserMapper 将在需要时初始化
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        data_dir = Path(__file__).parent / "data" / "auth"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.permissions_file = data_dir / "permissions.json"
        self.users_file = data_dir / "users.json"
        self.sessions_file = data_dir / "sessions.json"

    def _create_default_config(self) -> SubnetConfig:
        """创建默认配置"""
        return SubnetConfig(
            subnet_name="AuthNet", subnet_id="subnet.auth", version="1.0.0", enabled=True, log_level="INFO"
        )

    def load_permissions(self):
        """加载权限配置"""
        if self.permissions_file.exists():
            try:
                with open(self.permissions_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载权限配置失败: {e}")
                return self._create_default_permissions()
        else:
            config = self._create_default_permissions()
            # 保存默认配置
            self.save_permissions(config)
            return config

    def _create_default_permissions(self):
        """创建默认权限配置"""
        return {
            "default_permission_groups": ["Default"],
            "permission_hierarchy": {
                "*": ["*"],  # 超级管理员
                "admin": ["tool.*", "agent.*", "file.*"],
                "user": ["tool.*"],
                "guest": ["tool.get_current_time", "tool.web_search"],
            },
        }

    def save_permissions(self, config):
        """保存权限配置"""
        with open(self.permissions_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def load_users(self):
        """加载用户列表"""
        if self.users_file.exists():
            try:
                with open(self.users_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载用户列表失败: {e}")
                return {}
        else:
            return {}

    def save_users(self, users):
        """保存用户列表"""
        with open(self.users_file, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

    def load_sessions(self):
        """加载会话列表"""
        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载会话列表失败: {e}")
                return {}
        else:
            return {}

    def save_sessions(self, sessions):
        """保存会话列表"""
        with open(self.sessions_file, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)

    def _init_tools(self):
        """初始化鉴权工具"""
        try:
            from webnet.ToolNet.tools.auth.add_user import AddUserTool
            from webnet.ToolNet.tools.auth.check_permission import CheckPermissionTool
            from webnet.ToolNet.tools.auth.grant_permission import GrantPermissionTool
            from webnet.ToolNet.tools.auth.list_groups import ListGroupsTool
            from webnet.ToolNet.tools.auth.list_permissions import ListPermissionsTool
            from webnet.ToolNet.tools.auth.remove_user import RemoveUserTool
            from webnet.ToolNet.tools.auth.revoke_permission import RevokePermissionTool

            self.tools["check_permission"] = CheckPermissionTool()
            self.tools["grant_permission"] = GrantPermissionTool()
            self.tools["revoke_permission"] = RevokePermissionTool()
            self.tools["list_permissions"] = ListPermissionsTool()
            self.tools["list_groups"] = ListGroupsTool()
            self.tools["add_user"] = AddUserTool()
            self.tools["remove_user"] = RemoveUserTool()

            logger.info(f"[AuthNet] 已加载 {len(self.tools)} 个鉴权工具")
        except Exception as e:
            logger.warning(f"[AuthNet] 加载鉴权工具失败: {e}")
            self.tools = {}

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        message_type: Optional[str] = None,
        sender_name: Optional[str] = None,
    ) -> str:
        """执行鉴权工具"""
        try:
            tool = self.tools.get(tool_name)
            if not tool:
                self._record_failure(tool_name, "工具不存在")
                return f"工具 {tool_name} 不存在"

            context = {
                "user_id": user_id,
                "group_id": group_id,
                "message_type": message_type,
                "sender_name": sender_name,
                "subnet_name": "AuthNet",
            }

            result = await tool.execute(args, context)
            self._record_success(tool_name)
            return result
        except Exception as e:
            logger.error(f"[AuthNet] 执行工具 {tool_name} 失败: {e}")
            self._record_failure(tool_name, str(e))
            return f"执行失败: {str(e)}"

    def _record_success(self, tool_name: str):
        """记录成功操作"""
        # 可以添加审计日志

    def _record_failure(self, tool_name: str, error: str = "未知错误"):
        """记录失败操作"""
        logger.error(f"[AuthNet] 工具 {tool_name} 执行失败: {error}")

    def get_user_permissions(self, user_id: str) -> List[str]:
        """获取用户权限列表"""
        config = self.load_permissions()
        user_groups = config.get("users", {}).get(user_id, {}).get("groups", ["Default"])
        permissions = []

        for group in user_groups:
            group_perms = config.get("permission_hierarchy", {}).get(group, [])
            permissions.extend(group_perms)

        return list(set(permissions))

    def check_permission(self, user_id: str, permission: str) -> bool:
        """检查用户权限"""
        config = self.load_permissions()
        user_groups = config.get("users", {}).get(user_id, {}).get("groups", ["Default"])

        for group in user_groups:
            group_perms = config.get("permission_hierarchy", {}).get(group, [])
            if permission in group_perms or permission in ["*"]:
                return True

        return False

    def grant_permission(self, user_id: str, permission: str) -> bool:
        """授予用户权限"""
        config = self.load_permissions()

        if user_id not in config.get("users", {}):
            config["users"][user_id] = {"groups": ["Default"]}

        user_data = config["users"][user_id]
        if "groups" not in user_data:
            user_data["groups"] = []

        if permission not in user_data["groups"]:
            user_data["groups"].append(permission)

        self.save_permissions(config)
        return True

    def get_session_info(self, user_id: str) -> Optional[Dict]:
        """获取用户会话信息"""
        sessions = self.load_sessions()
        return sessions.get(user_id)

    def create_session(self, user_id: str, session_data: Dict) -> bool:
        """创建用户会话"""
        sessions = self.load_sessions()
        sessions[user_id] = session_data
        self.save_sessions(sessions)
        return True

    async def process_request(self, request: Dict[str, Any]) -> str:
        """处理鉴权请求"""
        action = request.get("action", "")
        user_id = str(request.get("user_id", ""))

        if action == "check_permission":
            permission = request.get("permission", "")
            result = await self.execute_tool(
                "check_permission", {"user_id": user_id, "permission": permission}, user_id
            )
            return json.dumps({"success": True, "has_permission": json.loads(result)}, ensure_ascii=False)

        elif action == "list_permissions":
            result = await self.execute_tool("list_permissions", {"user_id": user_id}, user_id)
            return json.dumps({"success": True, "permissions": json.loads(result)}, ensure_ascii=False)

        elif action == "list_groups":
            result = await self.execute_tool("list_groups", {}, user_id)
            return json.dumps({"success": True, "groups": json.loads(result)}, ensure_ascii=False)

        else:
            return json.dumps({"success": False, "error": "不支持的操作"}, ensure_ascii=False)
