"""LifeNet 创建阶段节点工具"""
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


class LifeCreateStageNode(BaseTool):
    """创建阶段节点工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "life_create_stage_node",
            "description": "创建阶段节点到LifeBook记忆系统。阶段节点用于记录人生不同阶段（如参加工作、大学毕业等）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "阶段名称"
                    },
                    "description": {
                        "type": "string",
                        "description": "阶段描述"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签列表（如 ['#工作', '#人生阶段']）"
                    }
                },
                "required": ["name"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行创建阶段节点"""
        life_net = context.lifenet
        if not life_net:
            return "❌ LifeNet 未初始化"

        name = args.get("name", "")
        if not name:
            return "❌ 请提供阶段名称"

        description = args.get("description", "")
        tags = args.get("tags")

        result = await life_net.handle_tool_call(
            "life_create_stage_node",
            {"name": name, "description": description, "tags": tags},
            {"lifenet": life_net}
        )

        return result


async def execute(args, context):
    """创建阶段节点（兼容旧接口）"""
    tool = LifeCreateStageNode()
    if isinstance(context, dict):
        from webnet.tools.base import ToolContext as TC
        context_obj = TC(lifenet=context.get("lifenet"))
        return await tool.execute(args, context_obj)
    return await tool.execute(args, context)
