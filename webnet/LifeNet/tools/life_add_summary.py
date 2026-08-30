"""LifeNet 添加总结工具"""
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


class LifeAddSummary(BaseTool):
    """添加总结工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "life_add_summary",
            "description": "添加总结（周/月/季/年）到LifeBook记忆系统。",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "description": "总结层级（weekly/monthly/quarterly/yearly）"
                    },
                    "title": {
                        "type": "string",
                        "description": "总结标题"
                    },
                    "content": {
                        "type": "string",
                        "description": "总结内容"
                    },
                    "capsule": {
                        "type": "string",
                        "description": "胶囊摘要（一句话概括）"
                    }
                },
                "required": ["level", "title", "content"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行添加总结"""
        life_net = context.lifenet
        if not life_net:
            return "❌ LifeNet 未初始化"

        level = args.get("level", "")
        title = args.get("title", "")
        content = args.get("content", "")
        capsule = args.get("capsule")

        result = await life_net.handle_tool_call(
            "life_add_summary",
            {"level": level, "title": title, "content": content, "capsule": capsule},
            {"lifenet": life_net}
        )

        return result


async def execute(args, context):
    """添加总结（兼容旧接口）"""
    tool = LifeAddSummary()
    if isinstance(context, dict):
        from webnet.tools.base import ToolContext as TC
        context_obj = TC(lifenet=context.get("lifenet"))
        return await tool.execute(args, context_obj)
    return await tool.execute(args, context)
