"""
技能检定工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any


class SkillCheck(BaseTool):
    """技能检定工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "skill_check",
            "description": "进行技能检定，自动计算修正值并返回判定结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "技能名称，如 '侦查'、'聆听'、'力量'"
                    },
                    "skill_value": {
                        "type": "integer",
                        "description": "技能值或属性值"
                    },
                    "rule_system": {
                        "type": "string",
                        "enum": ["coc7", "dnd5e"],
                        "description": "规则系统",
                        "default": "coc7"
                    },
                    "bonus": {
                        "type": "integer",
                        "description": "额外修正值（可选）",
                        "default": 0
                    }
                },
                "required": ["skill_name", "skill_value"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        skill_name = args.get("skill_name", "")
        skill_value = args.get("skill_value", 0)
        rule_system = args.get("rule_system", "coc7")
        bonus = args.get("bonus", 0)

        from ..dice import DiceEngine
        from ..character import get_character_manager

        # 获取角色卡
        character_manager = get_character_manager()
        pc = character_manager.get(context.user_id)

        if not pc:
            return f"❌ 请先创建角色卡：/pc create 角色名 {rule_system}"

        # 投骰
        dice = DiceEngine()

        if rule_system == "coc7":
            # COC7 技能检定
            from ..rules.coc7 import COC7Rules

            roll = dice.roll_percent()
            check_value = skill_value + bonus
            result = COC7Rules.check(roll, check_value)

            # 获取修正值说明
            modifier_text = f" (修正: +{bonus})" if bonus != 0 else ""

            return f"""🎲 **{skill_name}检定**

技能值：{skill_value}{modifier_text}
投骰：**{roll}** / {check_value}
结果：{result['result']}

{self._get_coc7_description(result)}"""

        elif rule_system == "dnd5e":
            # D&D 5E 技能检定
            from ..rules.dnd5e import DND5ERules

            # 获取属性值
            attr_map = {
                '力量': pc.dnd_strength,
                '敏捷': pc.dnd_dexterity,
                '体质': pc.dnd_constitution,
                '智力': pc.dnd_intelligence,
                '感知': pc.dnd_wisdom,
                '魅力': pc.dnd_charisma
            }

            attr_value = attr_map.get(skill_name, 10)
            proficiency = 2  # 默认熟练加值

            result = DND5ERules.skill_check(attr_value, proficiency + bonus, advantage=0)

            modifier = result['modifier'] + bonus
            total = result['roll'] + modifier

            return f"""🎲 **{skill_name}检定**

属性：{attr_value}
修正值：{modifier:+d}
投骰：**{result['roll']}** + {modifier} = **{total}**

{self._get_dnd5e_description(result)}"""

    def _get_coc7_description(self, result: Dict[str, Any]) -> str:
        """获取 COC7 判定描述"""
        descriptions = {
            5: "🌟 **大成功！** 效果翻倍，完美达成目标！",
            4: "✨ **极难成功！** 效果显著，超出预期！",
            3: "💪 **困难成功！** 表现出色，顺利达成！",
            2: "✅ **成功！** 基本达成目标。",
            1: "❌ **失败！** 未能达成目标。",
            -1: "💀 **大失败！** 灾难性后果！"
        }
        return descriptions.get(result['success_level'], "未知结果")

    def _get_dnd5e_description(self, result: Dict[str, Any]) -> str:
        """获取 D&D 5E 判定描述"""
        if result['critical']:
            return "🌟 **暴击！** 双倍伤害！"
        elif result['fumble']:
            return "💀 **大失败！** 可能触发严重后果！"
        elif result['total'] >= 15:
            return "✨ **优秀！** 表现非常出色！"
        elif result['total'] >= 10:
            return "✅ **成功！** 顺利达成目标。"
        else:
            return "❌ **失败！** 未能达成目标。"
