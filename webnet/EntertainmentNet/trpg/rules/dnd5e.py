"""
D&D 5E 规则系统
"""

from typing import Dict, Any


class DND5ERules:
    """D&D 5E 规则"""

    @staticmethod
    def get_modifier(score: int) -> int:
        """
        计算属性修正值

        Args:
            score: 属性值 (1-30)

        Returns:
            修正值 (-5 到 +10)
        """
        return (score - 10) // 2

    @staticmethod
    def ability_check(score: int, advantage: int = 0) -> Dict[str, Any]:
        """
        属性检定

        Args:
            score: 属性值
            advantage: 优势状态 (-1=劣势, 0=无, 1=优势)

        Returns:
            {
                'modifier': int,
                'roll': int,
                'total': int,
                'advantage': str
            }
        """
        import random

        modifier = DND5ERules.get_modifier(score)

        if advantage == 1:
            # 优势：取高
            roll1 = random.randint(1, 20)
            roll2 = random.randint(1, 20)
            roll = max(roll1, roll2)
            adv_text = f"优势 {roll1}/{roll2}"
        elif advantage == -1:
            # 劣势：取低
            roll1 = random.randint(1, 20)
            roll2 = random.randint(1, 20)
            roll = min(roll1, roll2)
            adv_text = f"劣势 {roll1}/{roll2}"
        else:
            # 无优势
            roll = random.randint(1, 20)
            adv_text = "无"

        total = roll + modifier

        return {
            'modifier': modifier,
            'roll': roll,
            'total': total,
            'advantage': adv_text,
            'critical': roll == 20,
            'fumble': roll == 1
        }

    @staticmethod
    def skill_check(score: int, proficiency: int = 0, advantage: int = 0) -> Dict[str, Any]:
        """
        技能检定

        Args:
            score: 属性值
            proficiency: 熟练加值
            advantage: 优势状态

        Returns:
            检定结果
        """
        result = DND5ERules.ability_check(score, advantage)
        modifier = result['modifier'] + proficiency
        total = result['roll'] + modifier

        return {
            'modifier': modifier,
            'roll': result['roll'],
            'total': total,
            'advantage': result['advantage'],
            'critical': result['critical'],
            'fumble': result['fumble']
        }

    @staticmethod
    def saving_throw(score: int, proficiency: int = 0, advantage: int = 0) -> Dict[str, Any]:
        """
        豁免检定

        Args:
            score: 属性值
            proficiency: 熟练加值
            advantage: 优势状态

        Returns:
            豁免结果
        """
        return DND5ERules.skill_check(score, proficiency, advantage)

    @staticmethod
    def attack_roll(attack_bonus: int, advantage: int = 0) -> Dict[str, Any]:
        """
        攻击检定

        Args:
            attack_bonus: 攻击加值
            advantage: 优势状态

        Returns:
            攻击结果
        """
        import random

        if advantage == 1:
            roll1 = random.randint(1, 20)
            roll2 = random.randint(1, 20)
            roll = max(roll1, roll2)
            adv_text = f"优势 {roll1}/{roll2}"
        elif advantage == -1:
            roll1 = random.randint(1, 20)
            roll2 = random.randint(1, 20)
            roll = min(roll1, roll2)
            adv_text = f"劣势 {roll1}/{roll2}"
        else:
            roll = random.randint(1, 20)
            adv_text = "无"

        total = roll + attack_bonus

        return {
            'modifier': attack_bonus,
            'roll': roll,
            'total': total,
            'advantage': adv_text,
            'critical': roll == 20,
            'fumble': roll == 1,
            'hit': total >= 10  # 默认 AC
        }

    @staticmethod
    def damage_roll(dice_str: str, modifier: int = 0, critical: bool = False) -> Dict[str, Any]:
        """
        伤害检定

        Args:
            dice_str: 骰子表达式，如 "2d6"
            modifier: 伤害修正
            critical: 是否暴击

        Returns:
            伤害结果
        """
        from ..dice import DiceEngine
        import re

        dice = DiceEngine()

        # 解析骰子表达式
        match = re.match(r'(\d+)d(\d+)', dice_str)
        if not match:
            return {'error': '无效的骰子表达式'}

        count = int(match.group(1))
        sides = int(match.group(2))

        # 暴击时骰子数量翻倍
        if critical:
            count *= 2

        result = dice.roll(f"{count}d{sides}")
        total = result.total + modifier

        return {
            'dice': dice_str,
            'roll': result.detail,
            'modifier': modifier,
            'total': total,
            'critical': critical
        }

    @staticmethod
    def initiative_check(dexterity: int, bonus: int = 0) -> int:
        """
        先攻检定

        Args:
            dexterity: 敏捷值
            bonus: 额外加值

        Returns:
            先攻值
        """
        import random
        modifier = DND5ERules.get_modifier(dexterity)
        roll = random.randint(1, 20)
        return roll + modifier + bonus
