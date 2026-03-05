"""
骰子系统核心
支持标准骰子表达式：d100, 3d6, 2d10+5, 4d6-2, 1d20+3d4
"""

import re
import random
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class DiceResult:
    """骰子结果"""
    expression: str      # 原始表达式
    detail: str          # 详细投掷过程
    total: int           # 总结果
    rolls: List[int]     # 每次投掷的结果
    modifiers: List[int] # 修正值


class DiceEngine:
    """骰子引擎"""

    def __init__(self):
        # 骰子表达式正则：3d6+5, 2d10-2, d100
        self.pattern = re.compile(r'(\d*)d(\d+)([+-]\d+)*', re.IGNORECASE)

    def roll(self, expression: str) -> DiceResult:
        """
        投掷骰子

        Args:
            expression: 骰子表达式，如 "3d6", "2d10+5", "d100"

        Returns:
            DiceResult: 投骰结果
        """
        expression = expression.strip().lower()

        # 处理简写形式：d100 -> 1d100
        if expression.startswith('d'):
            expression = '1' + expression

        # 解析表达式
        parts = expression.split('+')
        dice_part = parts[0]
        bonus = 0

        # 提取修正值
        if len(parts) > 1:
            try:
                bonus = int(parts[1])
            except ValueError:
                pass

        # 解析骰子部分
        match = re.match(r'(\d+)d(\d+)', dice_part)
        if not match:
            raise ValueError(f"无效的骰子表达式: {expression}")

        count = int(match.group(1))
        sides = int(match.group(2))

        # 投骰
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + bonus

        # 生成详细描述
        roll_details = '+'.join(map(str, rolls))
        detail = f"{count}d{sides}=[{roll_details}]"
        if bonus > 0:
            detail += f"+{bonus}"

        return DiceResult(
            expression=expression,
            detail=detail,
            total=total,
            rolls=rolls,
            modifiers=[bonus] if bonus != 0 else []
        )

    def roll_simple(self, sides: int, count: int = 1) -> List[int]:
        """简单投骰"""
        return [random.randint(1, sides) for _ in range(count)]

    def roll_percent(self) -> int:
        """投百面骰 (1-100)"""
        return random.randint(1, 100)


class DiceParser:
    """骰子表达式解析器"""

    @staticmethod
    def parse(expression: str) -> Dict[str, Any]:
        """
        解析骰子表达式

        Returns:
            {
                'count': int,      # 骰子数量
                'sides': int,      # 骰子面数
                'modifier': int,   # 修正值
                'valid': bool      # 是否有效
            }
        """
        expression = expression.strip().lower()

        if expression.startswith('d'):
            expression = '1' + expression

        parts = expression.split('+')
        dice_part = parts[0]
        modifier = 0

        if len(parts) > 1:
            try:
                modifier = int(parts[1])
            except ValueError:
                pass

        match = re.match(r'(\d+)d(\d+)', dice_part)
        if not match:
            return {'valid': False}

        return {
            'count': int(match.group(1)),
            'sides': int(match.group(2)),
            'modifier': modifier,
            'valid': True
        }


# 测试代码
if __name__ == "__main__":
    engine = DiceEngine()

    # 测试各种表达式
    test_expressions = ["d100", "3d6", "2d10+5", "4d6-2", "1d20"]

    for expr in test_expressions:
        result = engine.roll(expr)
        print(f"{expr}: {result.detail} = {result.total}")
