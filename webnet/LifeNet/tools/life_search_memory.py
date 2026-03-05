"""LifeNet 搜索记忆工具"""
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


class LifeSearchMemory(BaseTool):
    """搜索记忆工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "life_search_memory",
            "description": "在LifeBook记忆系统中搜索包含指定关键词的记忆条目。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "level": {
                        "type": "string",
                        "description": "层级过滤（daily/weekly/monthly/quarterly/yearly）",
                        "enum": ["daily", "weekly", "monthly", "quarterly", "yearly"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "结果数量限制（默认5）",
                        "default": 5
                    }
                },
                "required": ["keyword"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行搜索记忆"""
        life_net = context.lifenet
        if not life_net:
            return "❌ LifeNet 未初始化"

        keyword = args.get("keyword", "")
        if not keyword:
            return "❌ 请提供搜索关键词"

        level = args.get("level")
        limit = args.get("limit", 5)

        result = await life_net.handle_tool_call(
            "life_search_memory",
            {"keyword": keyword, "level": level, "limit": limit},
            {"lifenet": life_net}
        )

        return result


async def execute(args, context):
    """搜索记忆（兼容旧接口）"""
    tool = LifeSearchMemory()
    if isinstance(context, dict):
        from webnet.tools.base import ToolContext as TC
        context_obj = TC(lifenet=context.get("lifenet"))
        return await tool.execute(args, context_obj)
    return await tool.execute(args, context)
