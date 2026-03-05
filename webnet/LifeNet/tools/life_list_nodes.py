"""LifeNet 列出节点工具"""
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


class LifeListNodes(BaseTool):
    """列出节点工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "life_list_nodes",
            "description": "列出LifeBook中的所有节点，可按类型过滤。",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_type": {
                        "type": "string",
                        "description": "节点类型（character角色/stage阶段）",
                        "enum": ["character", "stage"]
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行列出节点"""
        life_net = context.lifenet
        if not life_net:
            return "❌ LifeNet 未初始化"

        node_type = args.get("node_type")

        result = await life_net.handle_tool_call(
            "life_list_nodes",
            {"node_type": node_type},
            {"lifenet": life_net}
        )

        return result


async def execute(args, context):
    """列出节点（兼容旧接口）"""
    tool = LifeListNodes()
    if isinstance(context, dict):
        from webnet.tools.base import ToolContext as TC
        context_obj = TC(lifenet=context.get("lifenet"))
        return await tool.execute(args, context_obj)
    return await tool.execute(args, context)
