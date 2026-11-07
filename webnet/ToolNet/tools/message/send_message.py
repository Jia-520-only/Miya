"""
发送消息工具 - 迁移示例
从 MessageNet 迁移到 ToolNet
"""

import logging
from typing import Any, Dict, Optional

from webnet.ToolNet.base import BaseTool, resolve_platform_adapter

logger = logging.getLogger(__name__)


class SendMessageTool(BaseTool):
    """发送消息工具 - 迁移示例"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "send_message",
            "description": "发送消息到指定群或私聊。当用户需要发送消息时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "要发送的消息内容"},
                    "group_id": {
                        "type": ["integer", "string"],
                        "description": "群号或群 OpenID（可选，默认为当前群）",
                    },
                    "user_id": {
                        "type": ["integer", "string"],
                        "description": "用户ID或用户 OpenID（可选，用于私聊）",
                    },
                },
                "required": ["message"],
            },
        }

    async def execute(self, args: Dict, context=None) -> str:
        """
        发送消息

        Args:
            args: 工具参数字典 (message, group_id, user_id)
            context: 执行上下文

        Returns:
            执行结果字符串
        """
        args = args or {}
        actual_context = context

        message = args.get("message", "")
        target_group_id = args.get("group_id")
        target_user_id = args.get("user_id")

        if not message:
            return "❌ 消息内容不能为空"

        adapter = resolve_platform_adapter(actual_context)
        if adapter is None and getattr(actual_context, "platform", None) in {None, "qq", "aiocqhttp", "onebot"}:
            adapter = getattr(actual_context, "onebot_client", None)

        if adapter is None:
            # 尝试从 context 获取
            target_info = (
                f"group_{target_group_id}"
                if target_group_id
                else f"user_{target_user_id}"
                if target_user_id
                else "unknown"
            )
            logger.info(f"[send_message] 消息将通过响应路径发送: {message[:50]}...")
            return f"[FINAL]{message}|||TARGET:{target_info}"

        try:
            # 确定发送目标
            send_group_id = target_group_id
            if not send_group_id and not target_user_id and getattr(actual_context, "message_type", None) == "group":
                send_group_id = getattr(actual_context, "group_id", None)

            # 发送群消息
            if send_group_id:
                sent = await adapter.send_group_message(group_id=send_group_id, message=message)
                if not sent:
                    return "❌ 群消息发送失败，平台未确认投递"
                if actual_context is not None:
                    actual_context.message_sent_this_turn = True
                logger.info(f"已发送群消息到群 {send_group_id}")
                return f"✅ 消息已发送到群 {send_group_id}"

            # 发送私聊消息
            else:
                target_user_id = target_user_id or getattr(actual_context, "platform_user_id", None) or getattr(actual_context, "user_id", None)
                if not target_user_id:
                    return "❌ 需要指定群号或用户ID"
                sent = await adapter.send_private_message(user_id=target_user_id, message=message)
                if not sent:
                    return "❌ 私聊消息发送失败，平台未确认投递"
                if actual_context is not None:
                    actual_context.message_sent_this_turn = True
                logger.info(f"已发送私聊消息给用户 {target_user_id}")
                return f"✅ 消息已发送给用户 {target_user_id}"

        except Exception as e:
            logger.error(f"发送消息失败: {e}", exc_info=True)
            return f"❌ 发送消息失败: {str(e)}"
