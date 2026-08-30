"""
/summary 命令 — 总结最近的聊天记录
"""

from __future__ import annotations

import logging
from typing import Any, List

from config.config_utils import get_command_message

logger = logging.getLogger(__name__)


async def execute(args: List[str], context: Any) -> str:
    """执行 /summary 命令"""
    count = 50  # 默认条数
    description = ""

    for arg in args:
        arg = arg.strip()
        if arg.isdigit():
            count = min(int(arg), 500)
        elif arg.endswith(("h", "d", "w", "m")):
            pass  # time_range reserved for future use
        else:
            description = arg

    # 获取聊天记录
    recent_messages = []
    if context.history_manager:
        try:
            chat_id = context.group_id if context.group_id else context.user_id
            msg_type = "group" if context.group_id else "private"
            recent_messages = await context.history_manager.get_recent(chat_id, msg_type, limit=count)
        except Exception as e:
            logger.warning(f"获取聊天记录失败: {e}")

    if not recent_messages:
        try:
            from webnet.ToolNet.tools.message.get_recent_messages import (
                GetRecentMessagesTool,
            )

            tool = GetRecentMessagesTool()
            fake_args = {"limit": count}
            result = await tool.execute(fake_args, context)
            if result and "失败" not in result:
                recent_messages = [result]
        except Exception:
            pass

    if not recent_messages:
        return get_command_message("summary_no_messages")

    # 构建总结请求
    messages_text = ""
    for i, msg in enumerate(recent_messages[:count]):
        if isinstance(msg, dict):
            sender = msg.get("sender_name", msg.get("user_id", "?"))
            text = msg.get("content", msg.get("text", ""))
            messages_text += f"[{sender}]: {text}\n"
        else:
            messages_text += f"{msg}\n"

    if not messages_text.strip():
        return get_command_message("summary_empty")

    focus = f"重点关注: {description}" if description else ""
    summary_prompt = (
        f"请总结以下聊天记录的主要内容（{len(recent_messages)} 条消息）。\n"
        f"{focus}\n"
        f"用简洁的要点列出：\n"
        f"1. 主要话题\n"
        f"2. 重要讨论\n"
        f"3. 待办事项（如有）\n\n"
        f"聊天记录:\n{messages_text[:8000]}"
    )

    # 尝试调用 AI 总结
    if context.ai_client:
        try:
            result = await context.ai_client.chat_with_system_prompt(
                system_prompt="你是一个聊天记录总结助手。请用简洁的要点总结。",
                user_prompt=summary_prompt,
                tools=[],
            )
            if result:
                return str(result)
        except Exception as e:
            logger.warning(f"AI 总结失败: {e}")

    return f"聊天记录总结（最近 {len(recent_messages)} 条消息）：\n\n{messages_text[:2000]}"
