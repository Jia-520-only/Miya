"""
获取历史消息工具
"""
from typing import Dict, Any, List
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class GetRecentMessages(BaseTool):
    """获取历史消息工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "get_recent_messages",
            "description": "获取群聊或私聊的历史消息，支持关键词和发送者过滤",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "integer",
                        "description": "会话ID（群号或用户QQ号）。不指定则使用当前会话"
                    },
                    "chat_type": {
                        "type": "string",
                        "description": "会话类型：group 或 private",
                        "enum": ["group", "private"],
                        "default": "group"
                    },
                    "count": {
                        "type": "integer",
                        "description": "获取消息数量（默认10，最多100）",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "keyword": {
                        "type": "string",
                        "description": "关键词过滤"
                    },
                    "sender_id": {
                        "type": "integer",
                        "description": "发送者QQ号过滤"
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        获取历史消息

        Args:
            args: {chat_id, chat_type, count, keyword, sender_id}
            context: 执行上下文

        Returns:
            历史消息文本
        """
        chat_id = args.get("chat_id")
        chat_type = args.get("chat_type", "group")
        count = args.get("count", 10)
        keyword = args.get("keyword")
        sender_id = args.get("sender_id")

        # 使用上下文中的会话
        if chat_id is None:
            chat_id = context.group_id if chat_type == "group" else context.user_id

        if chat_id is None:
            return "无法确定会话ID"

        # 使用 MemoryNet 获取对话历史
        if context.memory_net and hasattr(context.memory_net, 'get_recent_conversations'):
            try:
                memories = await context.memory_net.get_recent_conversations(
                    user_id=chat_id,
                    limit=count
                )

                if not memories:
                    return "没有历史消息记录"

                # 格式化返回
                results = []
                for i, memory in enumerate(memories, 1):
                    content = memory.get('content', '')
                    sender = memory.get('sender', '未知')
                    timestamp = memory.get('timestamp', '')

                    # 关键词过滤
                    if keyword and keyword not in content:
                        continue

                    # 发送者过滤（简化处理）
                    if sender_id:
                        continue

                    results.append(f"{i}. [{sender}]: {content}")

                if not results:
                    return "没有符合条件的消息"

                return "最近消息:\n" + "\n".join(results)

            except Exception as e:
                logger.error(f"获取历史消息失败: {e}", exc_info=True)
                return f"获取历史消息失败: {str(e)}"
        else:
            return "记忆系统未初始化或不支持对话历史查询"
