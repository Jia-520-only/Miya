"""LifeNet 创建角色节点工具"""
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


class LifeCreateCharacterNode(BaseTool):
    """创建角色节点工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "life_create_character_node",
            "description": "创建角色节点到LifeBook记忆系统。角色节点用于记录重要人物信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "角色名称"
                    },
                    "description": {
                        "type": "string",
                        "description": "角色描述"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "标签列表（如 ['#朋友', '#同事']）"
                    }
                },
                "required": ["name"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行创建角色节点"""
        life_net = context.lifenet
        if not life_net:
            return "❌ LifeNet 未初始化"

        name = args.get("name", "")
        if not name:
            return "❌ 请提供角色名称"

        description = args.get("description", "")
        tags = args.get("tags")

        result = await life_net.handle_tool_call(
            "life_create_character_node",
            {"name": name, "description": description, "tags": tags},
            {"lifenet": life_net}
        )

        return result


async def execute(args, context):
    """创建角色节点（兼容旧接口）"""
    tool = LifeCreateCharacterNode()
    if isinstance(context, dict):
        from webnet.tools.base import ToolContext as TC
        context_obj = TC(lifenet=context.get("lifenet"))
        return await tool.execute(args, context_obj)
    return await tool.execute(args, context)
