"""
运势查询工具 handler
"""

from typing import Any, Dict

from webnet.ToolNet.tools.entertainment.horoscope import Horoscope


async def execute(args: Dict[str, Any], context: Any) -> str:
    """执行运势查询"""
    try:
        tool = Horoscope()
        result = await tool.execute(args, context)
        return result
    except Exception as e:
        return f"查询运势失败: {str(e)}"
