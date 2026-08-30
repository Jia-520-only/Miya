"""
添加用户工具
"""

import json
import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool

logger = logging.getLogger(__name__)


class AddUserTool(BaseTool):
    """添加用户工具（已禁用）"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "add_user",
            "description": "添加新用户到鉴权系统（已禁用 - 请使用配置文件）。可以指定用户名、平台和初始权限组。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户ID（格式: platform_id，如: qq_123, web_user456）"}
                },
                "required": ["user_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        """执行添加用户（已禁用）"""
        return json.dumps(
            {
                "success": False,
                "error": "添加用户功能已禁用",
                "message": "权限只能通过配置文件修改，不支持通过命令添加用户。",
                "instructions": "请编辑以下文件来添加用户：\n"
                "1. config/permissions.json\n\n"
                "编辑后需要重启系统才能生效。",
            },
            ensure_ascii=False,
            indent=2,
        )
