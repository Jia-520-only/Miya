"""
酒馆对话工具
TavernChat - 酒馆模式下的 AI 对话（记录消息）
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool
from webnet.EntertainmentNet.tavern.memory import TavernMemory


class TavernChat(BaseTool):
    """酒馆对话工具 - 记录对话消息"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "tavern_chat",
            "description": "记录酒馆对话消息（实际回复由AI生成）",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "用户消息"
                    }
                },
                "required": ["message"]
            }
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        message = args.get("message", "")
        chat_id = str(context.group_id or context.user_id)
        user_id = str(context.user_id)

        # 初始化记忆
        memory = TavernMemory()

        # 获取玩家偏好
        player_info = memory.get_player_info(user_id)
        traits = player_info.get("traits", {})

        # 保存用户消息
        memory.add_message(chat_id, "user", message)

        # 返回确认，让 AI 继续生成回复
        if traits:
            traits_str = ", ".join([f"{k}:{v}" for k, v in traits.items()])
            return f"[已记录消息: {message}。用户特质: {traits_str}。AI现在生成回复。]"
        else:
            return f"[已记录消息: {message}。AI现在生成回复。]"
