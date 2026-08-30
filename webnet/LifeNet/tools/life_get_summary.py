"""LifeNet 获取总结工具"""
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


class LifeGetSummary(BaseTool):
    """获取总结工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "life_get_summary",
            "description": "获取LifeBook中指定层级的总结内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "description": "总结层级（weekly/monthly/quarterly/yearly）"
                    },
                    "period": {
                        "type": "string",
                        "description": "周期（如：2025-W09, 2025-01, 2025-Q1, 2025）"
                    }
                },
                "required": ["level", "period"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行获取总结"""
        life_net = context.lifenet
        if not life_net:
            return "❌ LifeNet 未初始化"

        level = args.get("level", "")
        period = args.get("period", "")

        result = await life_net.handle_tool_call(
            "life_get_summary",
            {"level": level, "period": period},
            {"lifenet": life_net}
        )

        return result


async def execute(args, context):
    """获取总结（兼容旧接口）"""
    tool = LifeGetSummary()
    if isinstance(context, dict):
        from webnet.tools.base import ToolContext as TC
        context_obj = TC(lifenet=context.get("lifenet"))
        return await tool.execute(args, context_obj)
    return await tool.execute(args, context)
