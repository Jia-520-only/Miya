"""
AuthNet - 鉴权子网

职责：
- 统一用户身份管理（跨平台）
- 权限检查与验证
- 会话管理
- API访问控制

架构：
- 符合弥娅子网规范，继承BaseSubnet
- 提供工具化接口（check_permission, grant_permission等）
"""

import logging
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import asyncio

from webnet.subnet_base import BaseSubnet, SubnetConfig
from webnet.tools.base import BaseTool
from .user_mapper import UserMapper

logger = logging.getLogger(__name__)


class AuthSubnet(BaseSubnet):
    """鉴权子网"""

    def __init__(self, config: Optional[SubnetConfig] = None):
        """初始化鉴权子网"""
        super().__init__(config)
        self.user_mapper = UserMapper()
        self._ensure_data_dir()
        logger.info("[AuthNet] 鉴权子网初始化完成")

    def _create_default_config(self) -> SubnetConfig:
        """创建默认配置"""
        return SubnetConfig(
            subnet_name="AuthNet",
            subnet_id="subnet.auth",
            version="1.0.0"
        )

    def _init_tools(self):
        """初始化鉴权工具"""
        from .tools.check_permission import CheckPermissionTool
        from .tools.grant_permission import GrantPermissionTool
        from .tools.revoke_permission import RevokePermissionTool
        from .tools.list_permissions import ListPermissionsTool
        from .tools.list_groups import ListGroupsTool
        from .tools.add_user import AddUserTool
        from .tools.remove_user import RemoveUserTool
        
        # 注册工具（直接添加到self.tools字典）
        self.tools['check_permission'] = CheckPermissionTool()
        self.tools['grant_permission'] = GrantPermissionTool()
        self.tools['revoke_permission'] = RevokePermissionTool()
        self.tools['list_permissions'] = ListPermissionsTool()
        self.tools['list_groups'] = ListGroupsTool()
        self.tools['add_user'] = AddUserTool()
        self.tools['remove_user'] = RemoveUserTool()
        
        logger.info(f"[AuthNet] 已注册 {len(self.tools)} 个鉴权工具")

    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        message_type: Optional[str] = None,
        sender_name: Optional[str] = None
    ) -> str:
        """执行工具"""
        try:
            tool = self.tools.get(tool_name)
            if not tool:
                self._record_failure()
                return f"❌ 工具不存在: {tool_name}"

            # 构造上下文
            context = {
                'user_id': user_id,
                'group_id': group_id,
                'message_type': message_type,
                'sender_name': sender_name,
                'subnet_name': 'AuthNet'
            }

            # 执行工具
            result = await tool.execute(args, context)
            self._record_success()
            return result

        except Exception as e:
            self._record_failure()
            logger.error(f"执行工具 {tool_name} 失败: {e}", exc_info=True)
            return f"❌ 工具执行失败: {str(e)}"

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        data_dir = Path("data/auth")
        data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化权限数据文件
        users_file = data_dir / "users.json"
        if not users_file.exists():
            default_users = {
                "users": [
                    {
                        "user_id": "system_admin",
                        "username": "系统管理员",
                        "platform": "system",
                        "permissions": ["*"],
                        "permission_groups": ["SuperAdmin"],
                        "created_at": datetime.now().isoformat()
                    }
                ]
            }
            users_file.write_text(json.dumps(default_users, indent=2, ensure_ascii=False), encoding='utf-8')

        groups_file = data_dir / "groups.json"
        if not groups_file.exists():
            default_groups = {
                "groups": {
                    "SuperAdmin": {
                        "description": "超级管理员",
                        "permissions": ["*"]
                    },
                    "Admin": {
                        "description": "管理员",
                        "permissions": [
                            "system.config.*",
                            "user.manage.*",
                            "tool.*",
                            "agent.*",
                            "api.*"
                        ]
                    },
                    "Developer": {
                        "description": "开发者",
                        "permissions": [
                            "tool.code_generator",
                            "tool.file_access",
                            "api.github.push",
                            "agent.task.execute"
                        ]
                    },
                    "User": {
                        "description": "普通用户",
                        "permissions": [
                            "tool.web_search",
                            "tool.data_analyze",
                            "tool.chart_generate",
                            "api.read",
                            "api.access",
                            "agent.task.create"
                        ]
                    },
                    "Guest": {
                        "description": "访客",
                        "permissions": [
                            "tool.web_search",
                            "api.read"
                        ]
                    }
                }
            }
            groups_file.write_text(json.dumps(default_groups, indent=2, ensure_ascii=False), encoding='utf-8')

    def get_all_users(self) -> Dict[str, Any]:
        """获取所有用户"""
        users_file = Path("data/auth/users.json")
        if users_file.exists():
            return json.loads(users_file.read_text(encoding='utf-8'))
        return {"users": []}

    def get_all_groups(self) -> Dict[str, Any]:
        """获取所有权限组"""
        groups_file = Path("data/auth/groups.json")
        if groups_file.exists():
            return json.loads(groups_file.read_text(encoding='utf-8'))
        return {"groups": {}}

    def save_users(self, users_data: Dict[str, Any]):
        """保存用户数据"""
        users_file = Path("data/auth/users.json")
        users_file.write_text(
            json.dumps(users_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    def save_groups(self, groups_data: Dict[str, Any]):
        """保存权限组数据"""
        groups_file = Path("data/auth/groups.json")
        groups_file.write_text(
            json.dumps(groups_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
