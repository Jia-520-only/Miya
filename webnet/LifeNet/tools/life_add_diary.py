"""LifeNet 添加日记工具"""
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


class LifeAddDiary(BaseTool):
    """添加日记工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "life_add_diary",
            "description": "添加日记到LifeBook记忆系统。用于记录日常生活、心情、事件等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "日记内容（必填）"
                    },
                    "mood": {
                        "type": "string",
                        "description": "心情（可选）"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签列表（可选，如 ['#工作', '#开心']）"
                    }
                },
                "required": ["content"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行添加日记"""
        # 获取 LifeNet 子网
        life_net = context.lifenet
        if not life_net:
            return "❌ LifeNet 未初始化"

        content = args.get("content", "")
        if not content:
            return "❌ 请提供日记内容"

        mood = args.get("mood")
        tags = args.get("tags")

        result = await life_net.handle_tool_call(
            "life_add_diary",
            {"content": content, "mood": mood, "tags": tags},
            {"lifenet": life_net}
        )

        return result


# 保留旧函数以兼容简单调用方式
async def execute(args, context):
    """添加日记（兼容旧接口）"""
    tool = LifeAddDiary()
    # 如果context是dict，转换为ToolContext
    if isinstance(context, dict):
        from webnet.tools.base import ToolContext as TC
        context_obj = TC(lifenet=context.get("lifenet"))
        return await tool.execute(args, context_obj)
    return await tool.execute(args, context)
