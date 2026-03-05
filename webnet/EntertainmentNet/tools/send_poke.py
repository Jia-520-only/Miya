"""
戳一戳工具
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class SendPoke(BaseTool):
    """戳一戳工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "send_poke",
            "description": "给指定群成员发送戳一戳（拍一拍）。当用户说'戳我一下'、'拍一拍我'、'戳@某人'等时必须调用此工具。重要：此工具执行实际戳一拍操作，不要用文字回复，必须调用工具执行。群聊时需要group_id参数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_user_id": {
                        "type": "integer",
                        "description": "要戳的QQ号。如果用户没有明确指定，使用当前聊天用户的QQ号"
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "群号（群聊时必填）"
                    }
                },
                "required": ["target_user_id"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """发送戳一戳"""
        target_user_id = args.get("target_user_id")
        group_id = args.get("group_id", context.group_id)

        if target_user_id is None:
            return "请提供要戳的QQ号（target_user_id参数）"

        try:
            target_user_id = int(target_user_id)
        except (ValueError, TypeError):
            return "参数类型错误：target_user_id必须是整数"

        onebot_client = context.onebot_client
        if not onebot_client:
            return "戳一戳功能不可用（OneBot客户端未设置）"

        try:
            # 调用戳一戳 API
            if hasattr(onebot_client, 'send_poke'):
                await onebot_client.send_poke(target_user_id, group_id)
                return f"✅ 已戳了 QQ{target_user_id} 一下"
            else:
                return "戳一戳功能不可用（客户端不支持）"

        except Exception as e:
            logger.error(f"戳一戳失败: {e}", exc_info=True)
            return f"戳一戳失败：{str(e)}"
