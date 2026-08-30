"""
列出群成员工具
"""

import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool

logger = logging.getLogger(__name__)


class ListMembersTool(BaseTool):
    """列出群成员工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "list_members",
            "description": "列出群聊的所有成员（占位实现）",
            "parameters": {
                "type": "object",
                "properties": {"group_id": {"type": "integer", "description": "群号（可选，默认为当前群）"}},
            },
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        """执行列出群成员（占位实现）"""
        args.get("group_id")
        return "列出群成员功能占位实现"
