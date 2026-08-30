"""
退出游戏模式工具
ExitGame - 退出当前的跑团或酒馆模式，返回普通模式
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool
from webnet.EntertainmentNet.game_mode import get_game_mode_manager, GameModeType


class ExitGame(BaseTool):
    """退出游戏模式工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "exit_game",
            "description": "退出当前的游戏模式（跑团或酒馆），返回普通模式",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        # 获取聊天ID
        chat_id = str(context.group_id or context.user_id)

        # 获取模式管理器
        mode_manager = get_game_mode_manager()

        # 检查当前模式
        current_mode = mode_manager.get_mode(chat_id)
        if current_mode is None or current_mode.mode_type == GameModeType.NONE:
            return "当前不在游戏模式中哦～ 还有什么我可以帮你的吗？"

        # 管理员权限检查
        # 如果在群聊中，检查用户是否为群管理员或superadmin
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

            # 只有 superadmin 或群管理员才能退出游戏模式
            if not is_superadmin and not is_admin:
                return "⚠️ 只有群管理员或超级管理员才能结束游戏模式哦～"

        # 退出模式
        exited_mode = mode_manager.exit_mode(chat_id)

        # 生成退出消息
        mode_names = {
            GameModeType.TRPG: "跑团",
            GameModeType.TAVERN: "酒馆"
        }

        mode_name = mode_names.get(exited_mode, "游戏") if exited_mode else "游戏"

        messages = {
            GameModeType.TRPG: f"""🎲 **跑团模式已结束**

感谢大家的参与！本次冒险到此告一段落。

期待下次再一起开启新的冒险！🗡️✨

现在已回到普通模式，你可以：
• 和我正常聊天
• 使用所有功能
• 随时再次启动游戏模式

我是弥娅，随时待命！💙""",
            GameModeType.TAVERN: f"""🍺 **酒馆时光结束**

感谢你的光临，很高兴能和你度过这段时光。

无论何时想再回来，这间酒馆的大门永远为你敞开。☕✨

现在已回到普通模式，有什么需要帮忙的吗？

我是弥娅，随时待命！💙"""
        }

        return messages.get(exited_mode, f"已退出{mode_name}模式，欢迎回来～") if exited_mode else f"已退出{mode_name}模式，欢迎回来～"
