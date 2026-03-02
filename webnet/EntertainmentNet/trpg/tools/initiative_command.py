"""
先攻管理工具
InitiativeCommand - 管理战斗中的先攻轮次
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any


class StartCombat(BaseTool):
    """开始战斗"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "start_combat",
            "description": "开始新的战斗，初始化先攻轮次",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        group_id = context.group_id

        from ..initiative import get_initiative_manager

        manager = get_initiative_manager()
        combat_info = manager.start_combat(group_id)

        return f"⚔️ **战斗开始！**\n📊 请使用 add_initiative 添加先攻条目"


class AddInitiative(BaseTool):
    """添加先攻条目"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "add_initiative",
            "description": "添加角色或NPC到先攻轮次",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "角色名称"
                    },
                    "initiative": {
                        "type": "integer",
                        "description": "先攻值（通常为 1d20 + 敏捷修正）"
                    },
                    "dex_mod": {
                        "type": "integer",
                        "description": "敏捷修正值（用于相同先攻值排序）",
                        "default": 0
                    },
                    "is_npc": {
                        "type": "boolean",
                        "description": "是否为NPC",
                        "default": False
                    }
                },
                "required": ["name", "initiative"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        name = args.get("name", "")
        initiative = args.get("initiative", 0)
        dex_mod = args.get("dex_mod", 0)
        is_npc = args.get("is_npc", False)
        group_id = context.group_id

        from ..initiative import get_initiative_manager

        manager = get_initiative_manager()
        entry = manager.add_entry(group_id, name, initiative, dex_mod, is_npc)

        return f"➕ **{name}** 已加入先攻轮次\n🎲 先攻: {initiative}{'+' + str(dex_mod) if dex_mod > 0 else ''}{' (NPC)' if is_npc else ' (玩家)'}"


class NextTurn(BaseTool):
    """下一回合"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "next_turn",
            "description": "进入下一个角色的回合",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        group_id = context.group_id

        from ..initiative import get_initiative_manager

        manager = get_initiative_manager()
        turn_info = manager.next_turn(group_id)

        if not turn_info:
            return "❌ 没有活跃的战斗"

        lines = [
            f"📢 **第 {turn_info['round']} 轮**",
            f"👤 当前回合: **{turn_info['current_character']}**",
            f"🎲 先攻: {turn_info['initiative']}"
        ]

        if turn_info['is_npc']:
            lines.append("🤖 (NPC)")

        return "\n".join(lines)


class ShowInitiative(BaseTool):
    """显示先攻轮次"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "show_initiative",
            "description": "显示当前的先攻轮次顺序",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        group_id = context.group_id

        from ..initiative import get_initiative_manager

        manager = get_initiative_manager()
        order = manager.get_order(group_id)

        if not order:
            return "❌ 当前没有活跃的战斗"

        lines = [f"⚔️ **战斗轮次 (第 {order['round']} 轮)**\n"]

        current_idx = order['current_index']
        for idx, entry in enumerate(order['entries']):
            prefix = "▶️ " if idx == current_idx else "  "

            status_icon = ""
            if entry['status'] == 'defeated':
                status_icon = "💀 "
            elif entry['status'] == 'hidden':
                status_icon = "👁️ "

            role_type = "(NPC)" if entry['is_npc'] else "(玩家)"

            line = f"{prefix}{status_icon}{idx + 1}. **{entry['name']}** - {entry['initiative']} {role_type}"
            lines.append(line)

        return "\n".join(lines)


class EndCombat(BaseTool):
    """结束战斗"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "end_combat",
            "description": "结束当前战斗，清除先攻轮次",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        group_id = context.group_id

        from ..initiative import get_initiative_manager

        manager = get_initiative_manager()
        success = manager.end_combat(group_id)

        if success:
            return "⏸️ **战斗结束**\n✅ 先攻轮次已清除"
        else:
            return "❌ 当前没有活跃的战斗"
