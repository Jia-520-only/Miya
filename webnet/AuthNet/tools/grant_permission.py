"""
授予权限工具（已禁用）

注意：此工具已禁用，因为权限只能通过配置文件修改。
请编辑 config/permissions.json 或 config/permissions.yaml 文件来管理权限。
"""

import json
import logging
from typing import Dict, Any

from webnet.tools.base import BaseTool
from ..permission_core import PermissionCore

logger = logging.getLogger(__name__)


class GrantPermissionTool(BaseTool):
    """授予权限工具（已禁用 - 请使用配置文件）"""

    def __init__(self):
        super().__init__()
        self.permission_core = PermissionCore(use_unified_config=True)

        self._config = {
            'name': 'grant_permission',
            'description': '授予用户权限（已禁用 - 请使用配置文件）',
            'parameters': {
                'type': 'object',
                'properties': {
                    'user_id': {
                        'type': 'string',
                        'description': '用户ID（格式: platform_id，如: qq_123, web_user456）'
                    },
                    'permission': {
                        'type': 'string',
                        'description': '权限节点（如: tool.web_search, agent.task.execute）'
                    },
                    'username': {
                        'type': 'string',
                        'description': '用户名（可选，用于创建新用户时）'
                    },
                    'platform': {
                        'type': 'string',
                        'description': '平台（可选，如: qq, web, desktop, terminal）'
                    }
                },
                'required': ['user_id', 'permission']
            }
        }

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    async def execute(self, args: Dict[str, Any], context) -> str:
        """执行权限授予（已禁用）"""
        return json.dumps({
            "success": False,
            "error": "授予权限功能已禁用",
            "message": "权限只能通过配置文件修改，不支持通过命令授予权限。",
            "instructions": "请编辑以下文件之一来管理权限：\n"
                          "1. config/permissions.json\n"
                          "2. config/permissions.yaml\n\n"
                          "编辑后需要重启系统才能生效。"
        }, ensure_ascii=False, indent=2)
