"""
AI 唱歌工具 handler
让 AI 可以主动调用弥娅的唱歌功能
"""

from typing import Any, Dict

from core.singing.engine_router import handle_sing_request


async def execute(args: Dict[str, Any], context: Any) -> str:
    try:
        song_name = args.get("song_name", "")
        username = args.get("username", "亲爱的")
        if not song_name:
            return "请告诉我你想听什么歌呢？"
        result = await handle_sing_request(song_name, username=username)
        return result
    except Exception as e:
        return f"唱歌功能调用失败: {str(e)}"
