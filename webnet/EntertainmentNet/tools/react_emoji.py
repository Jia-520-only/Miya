"""
表情回应工具
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class ReactEmoji(BaseTool):
    """表情回应工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "react_emoji",
            "description": "对指定消息使用表情回应。当用户明确要求对某条消息使用表情回应时调用此工具。重要：需要用户提供消息ID和表情ID，这些参数通常来自用户的明确指示或上下文。",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "integer",
                        "description": "要回应的消息ID"
                    },
                    "emoji_id": {
                        "type": "integer",
                        "description": "表情ID"
                    }
                },
                "required": ["message_id", "emoji_id"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """表情回应"""
        message_id = args.get("message_id")
        emoji_id = args.get("emoji_id")

        if message_id is None or emoji_id is None:
            return "请提供消息ID和表情ID"

        try:
            message_id = int(message_id)
            emoji_id = int(emoji_id)
        except (ValueError, TypeError):
            return "参数类型错误：message_id和emoji_id必须是整数"

        onebot_client = context.onebot_client
        if not onebot_client:
            return "表情回应功能不可用（OneBot客户端未设置）"

        try:
            # 调用表情回应 API
            if hasattr(onebot_client, 'set_msg_emoji_like'):
                await onebot_client.set_msg_emoji_like(message_id, emoji_id)
                return f"✅ 已对消息 {message_id} 使用表情 {emoji_id} 回应"
            else:
                return "表情回应功能不可用（客户端不支持）"

        except Exception as e:
            logger.error(f"表情回应失败: {e}", exc_info=True)
            return f"表情回应失败：{str(e)}"
