"""
消息表情回复工具 handler
"""

from typing import Any, Dict

from webnet.ToolNet.tools.entertainment.react_emoji import ReactEmoji


async def execute(args: Dict[str, Any], context: Any) -> str:
    """执行表情回复"""
    try:
        tool = ReactEmoji()
        result = await tool.execute(args, context)
        return result
    except Exception as e:
        return f"表情回复失败: {str(e)}"
