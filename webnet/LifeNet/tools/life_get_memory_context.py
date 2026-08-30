"""LifeNet 获取记忆上下文工具"""
from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext


class LifeGetMemoryContext(BaseTool):
    """一键获取记忆上下文工具（LifeBook核心功能）"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "life_get_memory_context",
            "description": "一键获取LifeBook记忆上下文。根据时间滚动获取记忆：年度总结（长期记忆）、季度总结、月度总结（中期记忆）、周度总结、最近日记（短期记忆）、关键人物与阶段节点。这是LifeBook的核心功能。",
            "parameters": {
                "type": "object",
                "properties": {
                    "months_back": {
                        "type": "integer",
                        "description": "回溯月数（可选，默认 1）",
                        "default": 1
                    },
                    "include_nodes": {
                        "type": "boolean",
                        "description": "是否包含节点信息（可选，默认 True）",
                        "default": True
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行获取记忆上下文"""
        life_net = context.lifenet
        if not life_net:
            return "❌ LifeNet 未初始化"

        months_back = args.get("months_back", 1)
        include_nodes = args.get("include_nodes", True)

        result = await life_net.handle_tool_call(
            "life_get_memory_context",
            {"months_back": months_back, "include_nodes": include_nodes},
            {"lifenet": life_net}
        )

        return result


# 保留旧函数以兼容简单调用方式
async def execute(args, context):
    """获取记忆上下文（兼容旧接口）"""
    tool = LifeGetMemoryContext()
    if isinstance(context, dict):
        from webnet.tools.base import ToolContext as TC
        context_obj = TC(lifenet=context.get("lifenet"))
        return await tool.execute(args, context_obj)
    return await tool.execute(args, context)
