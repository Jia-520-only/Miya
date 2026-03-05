"""
启动酒馆模式工具
StartTavern - 初始化酒馆会话
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool
from webnet.EntertainmentNet.tavern.memory import TavernMemory
from webnet.EntertainmentNet.game_mode import get_game_mode_manager, GameModeType


class StartTavern(BaseTool):
    """启动酒馆模式工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "start_tavern",
            "description": "启动酒馆模式，进入温暖的故事时光。启动后只能使用酒馆相关工具",
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
        # 管理员权限检查（仅在群聊中）
        if context.group_id and hasattr(context, 'superadmin'):
            group_id = context.group_id
            user_id = context.user_id
            superadmin = context.superadmin

            # 检查是否为 superadmin
            is_superadmin = (superadmin and user_id == superadmin)

            # 检查用户是否为群管理员
            is_admin = False
            if hasattr(context, 'onebot_client') and context.onebot_client:
                try:
                    member_info = await context.onebot_client.get_group_member_info(
                        group_id=group_id,
                        user_id=user_id
                    )
                    is_admin = member_info.get('role', 'member') in ['admin', 'owner']
                except Exception as e:
                    self.logger.warning(f"检查群管理员失败: {e}")

            # 只有 superadmin 或群管理员才能启动游戏模式
            if not is_superadmin and not is_admin:
                return "⚠️ 只有群管理员或超级管理员才能启动酒馆模式哦～"

        mood = args.get("mood", "warm")
        character_id = args.get("character", "miya")

        # 获取会话 ID（优先使用群 ID，否则使用用户 ID）
        chat_id = str(context.group_id or context.user_id)
        group_id = context.group_id
        user_id = context.user_id

        # 初始化记忆系统
        memory = TavernMemory()
        memory.set_mode(chat_id, "tavern")
        memory.set_mood(chat_id, mood)

        # 激活游戏模式
        mode_manager = get_game_mode_manager()
        mode_manager.set_mode(
            chat_id=chat_id,
            mode_type=GameModeType.TAVERN,
            prompt_key=f"tavern_{character_id}",
            extra_config={
                'mood': mood,
                'character': character_id
            },
            group_id=group_id,
            user_id=user_id
        )

        # 【新架构】设置游戏状态为 NOT_STARTED
        from webnet.EntertainmentNet.game_mode.mode_state import GameState
        mode_manager.set_game_state(chat_id, GameState.NOT_STARTED)

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

⚠️ **已进入酒馆沉浸模式**
• 现在只能使用酒馆相关功能
• 其他功能暂时不可用
• 输入 `/exit` 可退出酒馆模式

想聊聊天？还是想让我讲个故事？随便说些什么吧，我会认真倾听的～ ☕✨""",
            "tavern_keeper": f"""🍺 **欢迎来到老杰克的酒馆**

嘿，伙计！你来得正是时候！
这可是{mood_names[mood]}的好地方，{mood_descriptions[mood]}

我是老杰克，这里的酒保。来，找个舒服的座位坐下！

⚠️ **已进入酒馆沉浸模式**
• 现在只能使用酒馆相关功能
• 输入 `/exit` 可退出酒馆模式

想喝点什么？还是想听听我这些年收集的冒险故事？🍺""",
            "mysterious_traveler": f"""🌙 **神秘旅人的酒馆**

...你找到了这里。

这是一间{mood_names[mood]}的酒馆，{mood_descriptions[mood]}

我是来自远方的旅人...这里适合安静地交谈。

⚠️ **已进入酒馆沉浸模式**
• 现在只能使用酒馆相关功能
• 输入 `/exit` 可退出酒馆模式

你想说些什么吗？还是想听一些...特别的故事？"""
        }

        return welcome_messages.get(character_id, welcome_messages["miya"])
