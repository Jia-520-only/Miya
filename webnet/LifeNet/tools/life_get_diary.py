"""LifeNet 获取日记工具"""
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


class LifeGetDiary(BaseTool):
    """获取日记工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "life_get_diary",
            "description": "获取指定日期的日记。如果不指定日期，默认获取今天的日记。",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "日期（格式：YYYY-MM-DD），可选，默认为今天"
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行获取日记"""
        life_net = context.lifenet
        if not life_net:
            return "❌ LifeNet 未初始化"

        date = args.get("date")

        result = await life_net.handle_tool_call(
            "life_get_diary",
            {"date": date},
            {"lifenet": life_net}
        )

        return result


async def execute(args, context):
    """获取日记（兼容旧接口）"""
    tool = LifeGetDiary()
    if isinstance(context, dict):
        from webnet.tools.base import ToolContext as TC
        context_obj = TC(lifenet=context.get("lifenet"))
        return await tool.execute(args, context_obj)
    return await tool.execute(args, context)
