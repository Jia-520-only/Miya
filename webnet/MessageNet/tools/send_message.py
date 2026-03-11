"""
发送消息工具
"""
from typing import Dict, Any
import logging
import re
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class SendMessageTool(BaseTool):
    """发送消息工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "send_message",
            "description": "发送消息到群聊或私聊，支持@功能",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "要发送的消息内容"
                    },
                    "target_type": {
                        "type": "string",
                        "description": "目标会话类型：group(群聊) 或 private(私聊)",
                        "enum": ["group", "private"],
                        "default": "group"
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "目标会话ID（群号或用户QQ号）。如果不指定，使用当前上下文的群号/用户号"
                    }
                },
                "required": ["message"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        发送消息

        Args:
            args: {message, target_type, target_id}
            context: 执行上下文

        Returns:
            发送结果
        """
        message = args.get("message", "")
        target_type = args.get("target_type", "group")
        target_id = args.get("target_id")

        if not message:
            return "消息内容不能为空"

        # 解析目标会话
        if target_id is None:
            if target_type == "group":
                target_id = context.group_id
            elif target_type == "private":
                target_id = context.user_id

        if target_id is None:
            return "无法确定目标会话ID，请指定target_id参数"

        # 优先使用 onebot_client，兼容旧代码
        onebot_client = context.onebot_client
        if not onebot_client:
            # 如果 onebot_client 不可用，尝试使用 qq_net（兼容旧逻辑）
            if not context.qq_net:
                return "发送消息功能不可用（OneBot客户端未设置）"
            onebot_client = getattr(context.qq_net, 'onebot_client', None)
            if not onebot_client:
                return "发送消息功能不可用（无法获取OneBot客户端）"

        try:
            # 发送消息
            if target_type == "group":
                await onebot_client.send_group_message(target_id, message)
                result = f"已发送群消息: {message[:50]}..."
            else:
                await onebot_client.send_private_message(target_id, message)
                result = f"已发送私聊消息: {message[:50]}..."

            # 标记已发送
            context.message_sent_this_turn = True
            return result

        except Exception as e:
            logger.error(f"发送消息失败: {e}", exc_info=True)
            return f"发送消息失败: {str(e)}"
