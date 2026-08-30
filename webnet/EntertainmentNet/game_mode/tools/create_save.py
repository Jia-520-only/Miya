"""
创建游戏存档工具
CreateSave - 为当前游戏创建新存档
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext
from webnet.EntertainmentNet.game_mode.game_memory_manager import get_game_memory_manager
from webnet.EntertainmentNet.game_mode import get_game_mode_manager


class CreateSave(BaseTool):
    """创建游戏存档工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "create_game_save",
            "description": "为当前游戏创建新存档，保存当前的进度状态（角色卡、故事进度、对话历史等）。当用户说'存档'、'保存进度'、'创建存档'、'记录进度'等时必须调用此工具。重要：此工具执行实际存档操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "save_name": {
                        "type": "string",
                        "description": "存档名称（如：第一章结束、战胜BOSS等）"
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        from webnet.EntertainmentNet.game_mode.mode_state import GameState
        from webnet.EntertainmentNet.game_mode.state_transition_validator import StateTransitionValidator

        save_name = args.get("save_name", "未命名存档")
        mode_manager = get_game_mode_manager()
        game_memory_manager = get_game_memory_manager()

        # 获取当前聊天ID
        chat_id = str(context.group_id or context.user_id)

        # 获取当前游戏模式
        current_mode = mode_manager.get_mode(chat_id)
        if not current_mode or not current_mode.game_id:
            return "⚠️ 当前没有活跃的游戏，请先启动游戏模式\n💡 使用 `start_trpg` 启动跑团，或使用 `start_tavern` 启动酒馆"

        game_id = current_mode.game_id
        current_state = current_mode.game_state

        # 检查是否允许保存
        if not StateTransitionValidator.can_save(current_state):
            return f"⚠️ 当前状态为 {current_state.value}，不允许创建存档\n💡 请等待游戏开始后再保存"

        self.logger.info(f"[CreateSave] 为游戏 {game_id} 创建存档: {save_name}")

        try:
            # 使用 GameMemoryManager 保存游戏
            save_id = game_memory_manager.save_game(game_id, save_name)

            if save_id:
                from datetime import datetime
                game_metadata = game_memory_manager.get_game_metadata(game_id)
                game_name = game_metadata.game_name if game_metadata else "未知游戏"

                # 存档后状态改为 PAUSED，允许再次调用 load_game_save
                mode_manager.set_game_state(chat_id, GameState.PAUSED)

                self.logger.info(f"[CreateSave] 存档完成，游戏状态已设置为 PAUSED（允许加载存档）")

                return f"""✅ **存档创建成功**

🎮 **游戏**: {game_name}
🆔 **存档ID**: {save_id}
📝 **存档名称**: {save_name}
🕐 **创建时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💡 已保存：
  • 角色卡数据
  • 故事进度
  • 游戏状态
  • 对话历史

🔄 **提示**: 存档后可以使用 `load_game_save` 加载存档"""
            else:
                return f"⚠️ 创建存档失败，游戏ID: {game_id}"

        except Exception as e:
            self.logger.error(f"[CreateSave] 创建存档异常: {e}", exc_info=True)
            return f"⚠️ 创建存档时发生错误: {e}"
