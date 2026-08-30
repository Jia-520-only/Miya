"""
拍一拍工具 handler
"""

from typing import Any, Dict

from webnet.ToolNet.tools.entertainment.send_poke import SendPoke


async def execute(args: Dict[str, Any], context: Any) -> str:
    """执行拍一拍"""
    try:
        tool = SendPoke()
        result = await tool.execute(args, context)
        return result
    except Exception as e:
        return f"拍一拍失败: {str(e)}"
