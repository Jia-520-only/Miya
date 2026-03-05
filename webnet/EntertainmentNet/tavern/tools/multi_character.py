"""
多角色互动工具
MultiCharacterInteraction - 支持多个角色同时在场对话
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any, List


class StartMultiChat(BaseTool):
    """开启多角色对话"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "start_multi_chat",
            "description": "开启多角色对话模式，指定在场的角色列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "characters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "在场的角色名称列表"
                    }
                },
                "required": ["characters"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        characters = args.get("characters", [])
        chat_id = str(context.group_id or context.user_id)

        if not characters:
            return "❌ 请指定至少一个角色"

        from ..character import get_character_manager
        from ..memory import TavernMemory

        char_manager = get_character_manager()
        memory = TavernMemory()

        # 验证角色存在
        available = char_manager.list_all()
        available_names = [char['name'] for char in available]

        invalid = [c for c in characters if c not in available_names]
        if invalid:
            return f"❌ 以下角色不存在: {', '.join(invalid)}"

        # 设置多角色模式
        memory.set_mode(chat_id, f"multi_chat:{','.join(characters)}")

        # 获取角色简介
        chars_info = []
        for char_name in characters:
            char = char_manager.get(char_name)
            if char:
                chars_info.append(f"• {char_name}: {char.personality[:50]}...")

        lines = [
            f"🎭 **多角色对话模式已开启**",
            f"",
            f"在场的角色:",
            *chars_info,
            "",
            f"💡 现在你可以与这些角色进行对话，AI将根据各角色的性格生成回复"
        ]

        return "\n".join(lines)


class MultiCharacterChat(BaseTool):
    """多角色对话"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "multi_character_chat",
            "description": "在多角色模式下进行对话",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "对话消息"
                    }
                },
                "required": ["message"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        message = args.get("message", "")
        chat_id = str(context.group_id or context.user_id)

        from ..memory import TavernMemory
        from ..character import get_character_manager

        memory = TavernMemory()
        char_manager = get_character_manager()

        # 获取会话历史，判断是否在多角色模式
        recent = memory.get_recent_messages(chat_id, limit=5)
        if not recent:
            return "❌ 请先使用 start_multi_chat 开启多角色对话模式"

        # 查找最近的模式切换
        mode_msg = None
        for msg in reversed(recent):
            if msg['role'] == 'system' and 'multi_chat:' in msg['content']:
                mode_msg = msg['content']
                break

        if not mode_msg:
            return "❌ 未检测到多角色对话模式，请使用 start_multi_chat 开启"

        # 解析角色列表
        characters_str = mode_msg.split('multi_chat:')[1]
        character_names = characters_str.split(',')

        # 记录用户消息
        memory.add_message(chat_id, "user", message)

        # 获取角色信息
        chars_info = []
        for char_name in character_names:
            char = char_manager.get(char_name)
            if char:
                chars_info.append({
                    'name': char_name,
                    'personality': char.personality,
                    'speaking_style': char.speaking_style
                })

        # 返回上下文信息，让AI生成多角色回复
        chars_summary = ", ".join([c['name'] for c in chars_info])

        return f"[多角色对话] 当前在场角色: {chars_summary}。用户说: {message}。请根据各角色的性格，生成多个角色的回复。]"


class SetCharacterFocus(BaseTool):
    """设置焦点角色"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "set_character_focus",
            "description": "设置对话的焦点角色（优先回复）",
            "parameters": {
                "type": "object",
                "properties": {
                    "character": {
                        "type": "string",
                        "description": "角色名称"
                    }
                },
                "required": ["character"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        character = args.get("character", "")
        chat_id = str(context.group_id or context.user_id)

        if not character:
            return "❌ 请指定角色名称"

        from ..memory import TavernMemory
        memory = TavernMemory()

        memory.set_mode(chat_id, f"focus:{character}")

        return f"🎯 **焦点角色已设置为: {character}**\n💡 该角色将优先回复"
