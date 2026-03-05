"""
加载游戏存档工具
LoadSave - 加载指定的游戏存档
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext
from webnet.EntertainmentNet.game_mode.game_memory_manager import get_game_memory_manager
from webnet.EntertainmentNet.game_mode import get_game_mode_manager


class LoadSave(BaseTool):
    """加载游戏存档工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "load_game_save",
            "description": "加载当前游戏的存档，恢复游戏进度（角色卡、故事进度、对话历史等）。当用户说'加载存档'、'恢复存档'、'提取存档'、'读取存档'等时必须调用此工具。注意：加载存档会覆盖当前游戏状态。重要：如果用户说'继续游戏'，不要调用此工具，直接进行游戏叙事即可",
            "parameters": {
                "type": "object",
                "properties": {
                    "save_id": {
                        "type": "string",
                        "description": "存档ID（如 'autosave' 或从 list_game_saves 获取）。当前游戏只有一个存档，可以传 'autosave' 或不传"
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        from webnet.EntertainmentNet.game_mode.mode_state import GameState
        from webnet.EntertainmentNet.game_mode.state_transition_validator import (
            StateTransitionValidator, StateTransitionError
        )
        mode_manager = get_game_mode_manager()
        game_memory_manager = get_game_memory_manager()
        instance_manager = mode_manager.instance_manager

        # 获取当前聊天ID和用户ID
        chat_id = str(context.group_id or context.user_id)
        user_id = str(context.user_id)

        # 获取当前游戏模式
        current_mode = mode_manager.get_mode(chat_id)
        
        # 如果当前会话没有游戏,尝试查找用户的游戏
        if not current_mode or not current_mode.game_id:
            # 尝试通过用户ID查找游戏(处理跨会话情况)
            user_mode = mode_manager.get_mode(user_id)
            if user_mode and user_mode.game_id:
                return f"⚠️ 检测到你在私聊中启动了游戏,但当前在群聊中。\n\n💡 **解决方案**:\n1. 在私聊中使用'继续游戏'来继续游戏\n2. 或在群聊中重新启动游戏: `start_trpg`\n\n游戏ID: {user_mode.game_id}"
            
            return "⚠️ 当前没有活跃的游戏，请先启动游戏模式\n💡 使用 `start_trpg` 启动跑团，或使用 `start_tavern` 启动酒馆"

        # 【新架构】使用 StateTransitionValidator 验证状态
        current_state = current_mode.game_state

        # 检查是否允许加载
        if not StateTransitionValidator.can_load(current_state):
            return f"⚠️ 当前状态为 {current_state.value}，不允许加载存档\n💡 请先保存进度或暂停游戏"

        game_id = current_mode.game_id
        self.logger.info(f"[LoadSave] 加载游戏 {game_id} 的存档")

        try:
            # 转换到 LOADING 状态
            if not mode_manager.set_game_state(chat_id, GameState.LOADING):
                return "⚠️ 设置加载状态失败，请重试"

            # 使用 GameMemoryManager 加载游戏
            save_data = game_memory_manager.load_game(game_id)

            if save_data:
                from datetime import datetime
                game_metadata = game_memory_manager.get_game_metadata(game_id)
                game_name = game_metadata.game_name if game_metadata else "未知游戏"

                # 格式化时间
                created_at = save_data.created_at
                if created_at and created_at != '未知时间':
                    try:
                        dt = datetime.fromisoformat(created_at)
                        created_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass

                result = f"✅ **存档加载成功**\n\n"
                result += f"🎮 **游戏**: {game_name}\n"
                result += f"🆔 **存档ID**: {save_data.save_id}\n"
                result += f"📝 **存档名称**: {save_data.save_name}\n"
                result += f"🕐 **创建时间**: {created_at}\n\n"
                result += f"💾 游戏进度已恢复\n\n"
                result += f"🔄 **重要**: 游戏已恢复,用户说'继续游戏'或直接开始行动即可,无需重新调用start_trpg!\n\n"

                # 显示角色卡信息
                if save_data.characters:
                    result += "👥 **已加载角色卡**：\n"
                    for char_data in save_data.characters:
                        char_name = char_data.get('character_name', '未知角色')
                        char_id = char_data.get('character_id', '')
                        result += f"  • {char_name} (ID: {char_id[:8]}...)\n"
                    result += "\n"

                # 显示故事进度
                if save_data.story_progress:
                    result += "📜 **剧情进度**：\n"
                    for key, value in save_data.story_progress.items():
                        result += f"  • {key}: {value}\n"

                # 转换到 IN_PROGRESS 状态
                mode_manager.set_game_state(chat_id, GameState.IN_PROGRESS)

                self.logger.info(f"[LoadSave] 存档加载完成，游戏状态已设置为 IN_PROGRESS")

                return result
            else:
                # 加载失败，重置到安全状态
                safe_state = StateTransitionValidator.reset_to_safe_state(current_state)
                mode_manager.set_game_state(chat_id, safe_state)
                return f"⚠️ 加载存档失败，游戏ID: {game_id}"

        except Exception as e:
            self.logger.error(f"[LoadSave] 加载存档异常: {e}", exc_info=True)

            # 错误恢复：重置到安全状态
            try:
                safe_state = StateTransitionValidator.reset_to_safe_state(current_state)
                mode_manager.set_game_state(chat_id, safe_state)
                instance_manager.get_instance(chat_id).record_error()
            except:
                pass

            return f"⚠️ 加载存档时发生错误: {e}"
