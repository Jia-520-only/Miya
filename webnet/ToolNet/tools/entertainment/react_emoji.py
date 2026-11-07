"""
表情回应工具
"""

import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class ReactEmoji(BaseTool):
    """表情回应工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "react_emoji",
            "description": "对指定消息使用表情回应。QQ官方机器人仅支持频道消息；默认使用当前消息，不要臆造表情ID。OneBot 按其客户端能力处理。",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "要回应的消息ID；省略时使用当前消息"},
                    "emoji_id": {"type": "string", "description": "官方频道支持的系统表情ID或标准Emoji ID"},
                    "emoji_type": {"type": "integer", "enum": [1, 2], "description": "1为系统表情，2为标准Emoji，默认1"},
                },
                "required": ["emoji_id"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """表情回应"""
        message_id = args.get("message_id") or getattr(context, "message_id", None)
        emoji_id = args.get("emoji_id")
        emoji_type = args.get("emoji_type", 1)

        if emoji_id is None:
            return "请提供表情ID"
        if not message_id:
            return "请提供消息ID"

        try:
            emoji_type = int(emoji_type)
            if emoji_type not in (1, 2):
                raise ValueError("emoji_type")
        except (ValueError, TypeError):
            return "参数错误：emoji_type 必须为 1（系统表情）或 2（标准Emoji）"

        from webnet.ToolNet.base import resolve_platform_adapter

        adapter = resolve_platform_adapter(context)
        if adapter and getattr(adapter, "supports_channel_reaction", False):
            channel_id = getattr(context, "channel_id", None)
            if not channel_id:
                return "QQ 官方机器人目前仅支持频道消息表态；群聊和 C2C 暂不可用"
            try:
                ok = await adapter.set_channel_reaction(channel_id, message_id, str(emoji_id), emoji_type)
                return f"✅ 已对消息 {message_id} 添加表情回应" if ok else "表情回应失败：平台未确认操作成功"
            except Exception as e:
                logger.error("频道表情回应失败: %s", e, exc_info=True)
                return f"表情回应失败：{str(e)}"
        if adapter and getattr(adapter, "supports_emoji_reaction", False) and hasattr(adapter, "set_msg_emoji_like"):
            try:
                ok = await adapter.set_msg_emoji_like(message_id, emoji_id)
                if ok is False:
                    return "表情回应失败：平台未确认操作成功"
                return f"✅ 已对消息 {message_id} 使用表情 {emoji_id} 回应"
            except Exception as e:
                logger.error(f"表情回应失败: {e}", exc_info=True)
                return f"表情回应失败：{str(e)}"

        onebot_client = getattr(context, "onebot_client", None)
        if not onebot_client:
            return "表情回应功能不可用（平台不支持）"

        try:
            # 调用表情回应 API
            if hasattr(onebot_client, "set_msg_emoji_like"):
                ok = await onebot_client.set_msg_emoji_like(message_id, emoji_id)
                if ok is False:
                    return "表情回应失败：平台未确认操作成功"
                return f"✅ 已对消息 {message_id} 使用表情 {emoji_id} 回应"
            else:
                return "表情回应功能不可用（客户端不支持）"

        except Exception as e:
            logger.error(f"表情回应失败: {e}", exc_info=True)
            return f"表情回应失败：{str(e)}"
