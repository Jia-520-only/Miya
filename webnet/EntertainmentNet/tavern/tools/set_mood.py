"""
设置情绪工具
SetMood - 调整酒馆氛围
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool
from webnet.EntertainmentNet.tavern.memory import TavernMemory


class SetMood(BaseTool):
    """设置情绪工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "set_mood",
            "description": "调整酒馆的情绪氛围",
            "parameters": {
                "type": "object",
                "properties": {
                    "mood": {
                        "type": "string",
                        "enum": ["warm", "relaxed", "serious", "dark", "healing"],
                        "description": "新的情绪氛围"
                    }
                },
                "required": ["mood"]
            }
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        mood = args.get("mood", "warm")
        chat_id = str(context.group_id or context.user_id)

        # 设置情绪
        memory = TavernMemory()
        memory.set_mood(chat_id, mood)

        # 氛围映射
        mood_names = {
            "warm": "温暖",
            "relaxed": "轻松",
            "serious": "严肃",
            "dark": "暗黑",
            "healing": "治愈"
        }

        # 转换提示
        mood_messages = {
            "warm": "好的，让我把壁炉里的火调大一点，把灯光调暖一些... ☕🔥",
            "relaxed": "来了！换一首轻柔的爵士乐，放松身心吧～ 🎷✨",
            "serious": "明白，让我安静下来，我们可以深入地谈谈... 🌙",
            "dark": "烛光摇曳...你想听些更深沉的故事吗？🕯️",
            "healing": "温柔的光线下，有什么想倾诉的吗？我会用心听的... 💫"
        }

        return f"""✨ 酒馆氛围已调整为：**{mood_names[mood]}**

{mood_messages[mood]}

有什么想聊的吗？"""
