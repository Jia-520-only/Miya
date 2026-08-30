"""
戳一戳工具
"""

import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool

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
                        "description": "要戳的QQ号（纯数字，如123456789）。如果用户说'戳我'、'拍一拍我'，必须传递context.user_id的整数值（不是字符串，是纯数字QQ号）。",
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "群号（群聊时必填）",
                    },
                },
                "required": ["target_user_id"],
            },
        }

    async def execute(self, args: Dict, context) -> str:
        """发送戳一戳（走通用平台适配器）"""
        args = args or {}
        target_user_id = args.get("target_user_id")
        group_id = args.get("group_id") or getattr(context, "group_id", 0)
        user_id = getattr(context, "user_id", 0)

        if not target_user_id:
            target_user_id = user_id
        if not target_user_id:
            return "请指定要戳的用户"

        try:
            target_user_id = int(target_user_id)
            group_id = int(group_id) if group_id else 0
        except (ValueError, TypeError):
            pass

        from webnet.ToolNet.base import resolve_platform_adapter

        adapter = resolve_platform_adapter(context)
        if adapter and getattr(adapter, "supports_poke", False) and hasattr(adapter, "send_poke"):
            try:
                await adapter.send_poke(target_user_id, group_id)
                return f"✅ 戳了戳 {target_user_id}"
            except Exception as e:
                logger.error(f"戳一戳失败: {e}", exc_info=True)
                return f"戳一戳失败: {str(e)[:50]}"

        return "戳一戳功能暂不可用"
