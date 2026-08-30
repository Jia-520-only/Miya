"""
休息恢复工具
RestTool - 短休/长休恢复HP和MP
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any


class Rest(BaseTool):
    """休息恢复工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "rest",
            "description": "角色休息以恢复生命值和魔法值（短休恢复部分，长休恢复全部）",
            "parameters": {
                "type": "object",
                "properties": {
                    "rest_type": {
                        "type": "string",
                        "enum": ["short", "long"],
                        "description": "休息类型：short=短休（1小时），long=长休（8小时）"
                    },
                    "hit_dice": {
                        "type": "string",
                        "description": "短休使用的命中骰子（如1d8），仅D&D有效",
                        "default": "1d8"
                    }
                },
                "required": ["rest_type"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        rest_type = args.get("rest_type", "short")
        hit_dice = args.get("hit_dice", "1d8")
        user_id = context.user_id
        group_id = context.group_id

        from ..character import get_character_manager
        from ..dice import DiceEngine

        character_manager = get_character_manager()
        pc = character_manager.get(user_id)

        if not pc:
            return "❌ 请先创建角色卡"

        state = pc.get_state(group_id)
        dice = DiceEngine()

        if rest_type == "short":
            # 短休：恢复部分HP（COC: 恢复1d6，D&D: 使用命中骰子）
            if pc.rule_system == "coc7":
                recover_hp = dice.roll("1d6").total
                recover_mp = 0
                recover_san = 1
            else:  # dnd5e
                recover_hp = dice.roll(hit_dice).total
                recover_mp = dice.roll("1d4").total
                recover_san = 0

            # 应用恢复
            old_hp = state.hp
            state.hp = min(state.hp_max, state.hp + recover_hp)
            state.mp = min(state.mp_max, state.mp + recover_mp)
            state.san = min(99, state.san + recover_san)

            actual_hp = state.hp - old_hp
            actual_mp = state.mp + recover_mp - min(state.mp_max, state.mp + recover_mp)

            # 清除一些状态效果
            cleared_effects = []
            if "中毒" in state.status_effects:
                state.status_effects.remove("中毒")
                cleared_effects.append("中毒")

            character_manager.update(user_id, pc)

            lines = [
                f"⏸️ **{pc.character_name} 进行短休（1小时）**",
                f"📊 HP: {old_hp} → {state.hp} (+{actual_hp})",
            ]

            if actual_mp > 0:
                lines.append(f"📊 MP: {state.mp - actual_mp} → {state.mp} (+{actual_mp})")

            if recover_san > 0:
                lines.append(f"📊 SAN: {state.san - recover_san} → {state.san} (+{recover_san})")

            if cleared_effects:
                lines.append(f"✅ 清除状态: {', '.join(cleared_effects)}")

            return "\n".join(lines)

        elif rest_type == "long":
            # 长休：恢复所有HP/MP/SAN
            old_hp = state.hp
            old_mp = state.mp
            old_san = state.san

            state.hp = state.hp_max
            state.mp = state.mp_max
            state.san = min(99, state.san + 5)

            # 清除所有负面状态效果
            cleared_effects = state.status_effects.copy()
            state.status_effects.clear()

            character_manager.update(user_id, pc)

            lines = [
                f"🌙 **{pc.character_name} 进行长休（8小时）**",
                f"📊 HP: {old_hp} → {state.hp} (全满)",
                f"📊 MP: {old_mp} → {state.mp} (全满)",
                f"📊 SAN: {old_san} → {state.san} (+{state.san - old_san})"
            ]

            if cleared_effects:
                lines.append(f"✅ 清除状态: {', '.join(cleared_effects)}")

            return "\n".join(lines)

        return "❌ 未知的休息类型"
