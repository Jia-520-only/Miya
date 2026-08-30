"""
文昌帝君灵签工具 handler
"""

from typing import Any, Dict

from webnet.ToolNet.tools.entertainment.wenchang_dijun import WenchangDijun


async def execute(args: Dict[str, Any], context: Any) -> str:
    """执行文昌帝君抽签"""
    try:
        tool = WenchangDijun()
        result = await tool.execute(args, context)
        return result
    except Exception as e:
        return f"抽签失败: {str(e)}"
