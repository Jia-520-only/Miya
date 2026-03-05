"""
创建角色工具
CreateTavernCharacter - 创建酒馆角色
"""

from typing import Dict, Any
from webnet.tools.base import BaseTool
from webnet.EntertainmentNet.tavern.character import CharacterManager


class CreateTavernCharacter(BaseTool):
    """创建酒馆角色工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "create_tavern_character",
            "description": "创建一个新的酒馆角色",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_id": {
                        "type": "string",
                        "description": "角色ID（唯一标识）"
                    },
                    "name": {
                        "type": "string",
                        "description": "角色名称"
                    },
                    "personality": {
                        "type": "string",
                        "description": "性格描述"
                    },
                    "background": {
                        "type": "string",
                        "description": "背景故事"
                    },
                    "traits": {
                        "type": "string",
                        "description": "特质列表，用逗号分隔"
                    },
                    "speaking_style": {
                        "type": "string",
                        "description": "说话风格"
                    }
                },
                "required": ["character_id", "name", "personality", "speaking_style"]
            }
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        character_id = args.get("character_id", "")
        name = args.get("name", "")
        personality = args.get("personality", "")
        background = args.get("background", "")
        traits_str = args.get("traits", "")
        speaking_style = args.get("speaking_style", "")

        # 处理特质列表
        traits = [t.strip() for t in traits_str.split(",")] if traits_str else []

        # 创建角色
        manager = CharacterManager()
        character = manager.create_character(
            character_id=character_id,
            name=name,
            personality=personality,
            background=background,
            traits=traits,
            speaking_style=speaking_style
        )

        # 格式化输出
        traits_display = ", ".join(traits) if traits else "无"

        return f"""✅ 角色创建成功！

📋 **角色信息**
- ID: {character.character_id}
- 名称: {character.name}
- 性格: {character.personality}
- 特质: {traits_display}
- 说话风格: {character.speaking_style}

{f"- 背景: {character.background}" if background else ""}

角色已保存，可以在酒馆中使用啦！✨"""
