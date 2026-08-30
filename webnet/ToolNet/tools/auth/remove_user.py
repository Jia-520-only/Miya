"""
移除用户工具（已禁用）

注意：此工具已禁用，因为权限只能通过配置文件修改。
请编辑 config/permissions.json 文件来管理用户。
"""

import json
import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool

logger = logging.getLogger(__name__)


class RemoveUserTool(BaseTool):
    """移除用户工具（已禁用 - 请使用配置文件）"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "remove_user",
            "description": "从鉴权系统中移除用户（已禁用 - 请使用配置文件）",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "用户ID（格式: platform_id，如: qq_123, web_user456）"}
                },
                "required": ["user_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        """执行移除用户（已禁用）"""
        return json.dumps(
            {
                "success": False,
                "error": "移除用户功能已禁用",
                "message": "权限只能通过配置文件修改，不支持通过命令移除用户。",
                "instructions": "请编辑以下文件之一来管理用户：\n"
                "1. config/permissions.json\n\n"
                "编辑后需要重启系统才能生效。",
            },
            ensure_ascii=False,
            indent=2,
        )
