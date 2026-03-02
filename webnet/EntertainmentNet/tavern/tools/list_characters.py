"""
列出角色工具
ListTavernCharacters - 列出所有酒馆角色
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool
from webnet.EntertainmentNet.tavern.character import CharacterManager


class ListTavernCharacters(BaseTool):
    """列出酒馆角色工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "list_tavern_characters",
            "description": "列出所有可用的酒馆角色",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        manager = CharacterManager()
        character_ids = manager.list_characters()

        if not character_ids:
            return "目前没有可用的角色呢... 🤔"

        # 构建角色列表
        result = "🎭 **酒馆角色列表**\n\n"

        for char_id in character_ids:
            character = manager.get_character(char_id)
            if character:
                traits_display = ", ".join(character.traits[:3])  # 只显示前3个特质
                if len(character.traits) > 3:
                    traits_display += "..."

                result += f"""**{character.name}** (ID: {character.character_id})
性格: {character.personality}
特质: {traits_display}
对话次数: {character.message_count}

---

"""

        result += f"\n共 {len(character_ids)} 个角色\n\n使用 `/start_tavern character=<ID>` 可以切换角色 ✨"

        return result
