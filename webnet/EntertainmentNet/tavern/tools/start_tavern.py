"""
启动酒馆模式工具
StartTavern - 初始化酒馆会话
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool
from webnet.EntertainmentNet.tavern.memory import TavernMemory


class StartTavern(BaseTool):
    """启动酒馆模式工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "start_tavern",
            "description": "启动酒馆模式，进入温暖的故事时光",
            "parameters": {
                "type": "object",
                "properties": {
                    "mood": {
                        "type": "string",
                        "enum": ["warm", "relaxed", "serious", "dark", "healing"],
                        "description": "酒馆氛围",
                        "default": "warm"
                    },
                    "character": {
                        "type": "string",
                        "description": "选择角色（默认为弥娅）",
                        "default": "miya"
                    }
                }
            }
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        mood = args.get("mood", "warm")
        character_id = args.get("character", "miya")

        # 获取会话 ID（优先使用群 ID，否则使用用户 ID）
        chat_id = str(context.group_id or context.user_id)

        # 初始化记忆系统
        memory = TavernMemory()
        memory.set_mode(chat_id, "tavern")
        memory.set_mood(chat_id, mood)

        # 氛围映射
        mood_names = {
            "warm": "温暖",
            "relaxed": "轻松",
            "serious": "严肃",
            "dark": "暗黑",
            "healing": "治愈"
        }

        # 氛围描述
        mood_descriptions = {
            "warm": "温暖的小酒馆，壁炉里的火苗在轻轻跳动，空气中飘着烤面包的香气",
            "relaxed": "轻松惬意的小酒馆，爵士乐在低声流淌，适合放下一天的疲惫",
            "serious": "安静严肃的酒馆，适合深沉的思考和深入的对话",
            "dark": "昏暗神秘的酒馆，烛光摇曳，适合聆听那些不为人知的故事",
            "healing": "温柔的治愈酒馆，暖色调的灯光，适合抚平心中的伤痕"
        }

        # 欢迎语模板
        welcome_messages = {
            "miya": f"""🍺 **欢迎来到弥娅的深夜酒馆**

这里是一间{mood_names[mood]}的小酒馆。
{mood_descriptions[mood]}

我是老板娘弥娅，很高兴见到你。

想聊聊天？还是想让我讲个故事？随便说些什么吧，我会认真倾听的～ ☕✨""",
            "tavern_keeper": f"""🍺 **欢迎来到老杰克的酒馆**

嘿，伙计！你来得正是时候！
这可是{mood_names[mood]}的好地方，{mood_descriptions[mood]}

我是老杰克，这里的酒保。来，找个舒服的座位坐下！

想喝点什么？还是想听听我这些年收集的冒险故事？🍺""",
            "mysterious_traveler": f"""🌙 **神秘旅人的酒馆**

...你找到了这里。

这是一间{mood_names[mood]}的酒馆，{mood_descriptions[mood]}

我是来自远方的旅人...这里适合安静地交谈。

你想说些什么吗？还是想听一些...特别的故事？"""
        }

        return welcome_messages.get(character_id, welcome_messages["miya"])
