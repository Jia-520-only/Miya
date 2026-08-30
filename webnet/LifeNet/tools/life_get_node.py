"""LifeNet 获取节点详情工具"""
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


class LifeGetNode(BaseTool):
    """获取节点详情工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "life_get_node",
            "description": "获取LifeBook中指定节点的详细信息，包括相关记忆。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "节点名称"
                    }
                },
                "required": ["name"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行获取节点"""
        life_net = context.lifenet
        if not life_net:
            return "❌ LifeNet 未初始化"

        name = args.get("name", "")
        if not name:
            return "❌ 请提供节点名称"

        result = await life_net.handle_tool_call(
            "life_get_node",
            {"name": name},
            {"lifenet": life_net}
        )

        return result


async def execute(args, context):
    """获取节点（兼容旧接口）"""
    tool = LifeGetNode()
    if isinstance(context, dict):
        from webnet.tools.base import ToolContext as TC
        context_obj = TC(lifenet=context.get("lifenet"))
        return await tool.execute(args, context_obj)
    return await tool.execute(args, context)
