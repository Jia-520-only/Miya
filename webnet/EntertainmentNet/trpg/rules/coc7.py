"""
COC 7版规则系统
"""

from typing import Dict, Any
from enum import Enum


class CheckResult(Enum):
    """检定结果"""
    CRITICAL_SUCCESS = "大成功"
    EXTREME_SUCCESS = "极难成功"
    HARD_SUCCESS = "困难成功"
    SUCCESS = "成功"
    FAILURE = "失败"
    CRITICAL_FAILURE = "大失败"


class COC7Rules:
    """COC 7版规则"""

    @staticmethod
    def check(roll_value: int, skill_value: int) -> Dict[str, Any]:
        """
        d100 判定

        Args:
            roll_value: 投骰结果 (1-100)
            skill_value: 技能值

        Returns:
            {
                'result': '成功',
                'type': 'success',
                'success_level': 3  # 成功等级 (0-5)
            }
        """
        # 大成功
        if roll_value == 1:
            return {
                'result': CheckResult.CRITICAL_SUCCESS.value,
                'type': 'critical_success',
                'success_level': 5
            }

        # 大失败
        if roll_value == 100:
            return {
                'result': CheckResult.CRITICAL_FAILURE.value,
                'type': 'critical_failure',
                'success_level': -1
            }

        # 极难成功
        if roll_value <= skill_value // 5:
            return {
                'result': CheckResult.EXTREME_SUCCESS.value,
                'type': 'extreme_success',
                'success_level': 4
            }

        # 困难成功
        if roll_value <= skill_value // 2:
            return {
                'result': CheckResult.HARD_SUCCESS.value,
                'type': 'hard_success',
                'success_level': 3
            }

        # 成功
        if roll_value <= skill_value:
            return {
                'result': CheckResult.SUCCESS.value,
                'type': 'success',
                'success_level': 2
            }

        # 失败
        return {
            'result': CheckResult.FAILURE.value,
            'type': 'failure',
            'success_level': 1
        }

    @staticmethod
    def skill_check(roll_value: int, skill_value: int) -> str:
        """技能检定，返回格式化的结果字符串"""
        result = COC7Rules.check(roll_value, skill_value)

        emoji = "✅" if result['success_level'] >= 2 else "❌"
        return f"{emoji} 投骰值：{roll_value} / {skill_value} → **{result['result']}**"

    @staticmethod
    def get_modifier_success(success_level: int) -> str:
        """根据成功等级获取修正值说明"""
        modifiers = {
            5: "大成功！效果翻倍",
            4: "极难成功！获得加值",
            3: "困难成功！正常效果",
            2: "普通成功！正常效果",
            1: "失败！无效果",
            -1: "大失败！触发严重后果"
        }
        return modifiers.get(success_level, "未知结果")

    @staticmethod
    def calculate_derived_attrs(strength: int, dexterity: int, constitution: int,
                               power: int) -> Dict[str, int]:
        """计算衍生属性"""
        hp = constitution // 10
        mp = power // 5
        move_rate = (strength + dexterity) // 10

        db_str = (strength + constitution) // 10
        if db_str < 65:
            db_value = -1
            db_name = "-1"
        elif db_str < 85:
            db_value = 0
            db_name = "-1d4"
        elif db_str < 125:
            db_value = 1
            db_name = "1d4"
        elif db_str < 165:
            db_value = 2
            db_name = "1d6"
        else:
            db_value = 4
            db_name = "2d6"

        build = db_str // 10

        return {
            'hp': hp,
            'hp_max': hp,
            'mp': mp,
            'mp_max': mp,
            'move_rate': move_rate,
            'db_value': db_value,
            'db_name': db_name,
            'build': build
        }

    @staticmethod
    def sanity_check(san: int, san_cost: int) -> Dict[str, Any]:
        """
        理智检定

        Args:
            san: 当前理智值
            san_cost: 理智消耗

        Returns:
            {
                'success': bool,
                'roll_result': int,
                'new_san': int,
                'message': str
            }
        """
        import random
        from .dice import DiceEngine

        dice = DiceEngine()
        roll = dice.roll_percent()
        result = COC7Rules.check(roll, san)

        if result['success_level'] >= 2:
            # 成功，消耗 1d{san_cost}
            cost = random.randint(1, san_cost)
            new_san = max(0, san - cost)
            message = f"理智检定成功！{san} → {new_san} (-{cost})"
        else:
            # 失败，消耗 {san_cost}d{san_cost}
            cost = sum([random.randint(1, san_cost) for _ in range(san_cost)])
            new_san = max(0, san - cost)
            message = f"理智检定失败！{san} → {new_san} (-{cost})"

        return {
            'success': result['success_level'] >= 2,
            'roll_result': roll,
            'new_san': new_san,
            'message': message
        }
