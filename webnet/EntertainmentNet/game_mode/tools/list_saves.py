"""
列出游戏存档工具
ListSaves - 列出当前游戏的所有存档
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool, ToolContext
from webnet.EntertainmentNet.game_mode.game_memory_manager import get_game_memory_manager
from webnet.EntertainmentNet.game_mode import get_game_mode_manager
from core.constants import Encoding


class ListSaves(BaseTool):
    """列出游戏存档工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "list_game_saves",
            "description": "列出当前游戏的所有存档。当用户说'检查存档'、'查看存档'、'列出存档'、'存档列表'等时必须调用此工具。返回存档名称、创建时间等信息。",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        mode_manager = get_game_mode_manager()
        game_memory_manager = get_game_memory_manager()

        # 获取当前聊天ID
        chat_id = str(context.group_id or context.user_id)

        # 获取当前游戏模式
        current_mode = mode_manager.get_mode(chat_id)
        if not current_mode or not current_mode.game_id:
            return "📂 当前没有活跃的游戏，请先启动游戏模式\n💡 使用 `start_trpg` 启动跑团，或使用 `start_tavern` 启动酒馆"

        game_id = current_mode.game_id
        self.logger.info(f"[ListSaves] 查找游戏 {game_id} 的存档")

        # 查找游戏目录
        from pathlib import Path
        game_dir = game_memory_manager._find_game_path(game_id)

        if not game_dir.exists():
            return f"📂 游戏数据未找到 (游戏ID: {game_id})"

        # 检查是否有 save_data.json
        save_file = game_dir / "save_data.json"
        if not save_file.exists():
            return f"📂 游戏还没有存档记录 (游戏ID: {game_id})"

        # 读取存档数据
        try:
            import json
            from datetime import datetime

            data = json.loads(save_file.read_text(encoding=Encoding.UTF8))
            save_name = data.get('save_name', '未命名存档')
            created_at = data.get('created_at', '未知时间')
            save_id = data.get('save_id', 'autosave')

            # 格式化时间
            if created_at and created_at != '未知时间':
                try:
                    dt = datetime.fromisoformat(created_at)
                    created_at = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass

            # 获取游戏元数据
            game_metadata = game_memory_manager.get_game_metadata(game_id)
            game_name = game_metadata.game_name if game_metadata else "未知游戏"

            # 格式化输出
            result = f"📂 **游戏存档列表**\n\n"
            result += f"🎮 **游戏**: {game_name}\n"
            result += f"🆔 **存档ID**: {save_id}\n"
            result += f"📝 **存档名称**: {save_name}\n"
            result += f"🕐 **创建时间**: {created_at}\n\n"

            result += f"💡 使用 `create_game_save` 创建新存档覆盖当前存档\n"

            return result

        except Exception as e:
            self.logger.error(f"[ListSaves] 读取存档失败: {e}")
            return f"❌ 读取存档失败: {str(e)}"
