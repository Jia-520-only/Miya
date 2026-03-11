"""
添加用户工具
"""

import json
import logging
from typing import Dict, Any
from datetime import datetime

from webnet.tools.base import BaseTool
from ..permission_core import PermissionCore

logger = logging.getLogger(__name__)


class AddUserTool(BaseTool):
    """添加用户工具"""

    def __init__(self):
        super().__init__()
        self.permission_core = PermissionCore()
        
        self._config = {
            'name': 'add_user',
            'description': '添加新用户到鉴权系统。可以指定用户名、平台和初始权限组。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'user_id': {
                        'type': 'string',
                        'description': '用户ID（格式: platform_id，如: qq_123, web_user456）'
                    },
                    'username': {
                        'type': 'string',
                        'description': '用户名（可选，默认为user_id）'
                    },
                    'platform': {
                        'type': 'string',
                        'description': '平台（qq, web, desktop, terminal等）',
                        'default': 'unknown'
                    },
                    'permission_groups': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': '初始权限组列表（可选，默认为["Default"]）',
                        'default': ['Default']
                    }
                },
                'required': ['user_id']
            }
        }

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    async def execute(self, args: Dict[str, Any], context) -> str:
        """执行添加用户（已禁用）"""
        return json.dumps({
            "success": False,
            "error": "添加用户功能已禁用",
            "message": "权限只能通过配置文件修改，不支持通过命令添加用户。",
            "instructions": "请编辑以下文件之一来添加用户：\n"
                          "1. config/permissions.json\n"
                          "2. config/permissions.yaml\n\n"
                          "编辑后需要重启系统才能生效。"
        }, ensure_ascii=False, indent=2)
