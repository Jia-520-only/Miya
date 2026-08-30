"""
投骰工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any


class RollDice(BaseTool):
    """投骰工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "roll_dice",
            "description": "投掷骰子，支持格式如 3d6、2d10+5、1d100 等",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "骰子表达式，如 3d6、2d10+5、1d100"
                    },
                    "reason": {
                        "type": "string",
                        "description": "投骰原因（可选），如 '侦查检定'",
                        "default": ""
                    }
                },
                "required": ["expression"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        expression = args.get("expression", "")
        reason = args.get("reason", "")

        from ..dice import DiceEngine

        try:
            dice = DiceEngine()
            result = dice.roll(expression)

            if reason:
                return f"🎲 **{reason}**\n{result.detail} = **{result.total}**"
            return f"🎲 投骰结果\n{result.detail} = **{result.total}**"
        except Exception as e:
            return f"❌ 投骰失败：{str(e)}"
