"""
暗骰工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any


class RollSecret(BaseTool):
    """暗骰工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "roll_secret",
            "description": "暗骰，结果仅发送给 KP",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "骰子表达式"
                    },
                    "reason": {
                        "type": "string",
                        "description": "检定原因"
                    }
                },
                "required": ["expression"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        expression = args.get("expression", "")
        reason = args.get("reason", "")
        user_id = context.user_id
        group_id = context.group_id

        from ..dice import DiceEngine
        from ..session import get_session_manager

        # 获取当前群的 KP
        session_manager = get_session_manager()
        session = session_manager.get(group_id)

        if not session:
            return "❌ 当前群未启动跑团模式，请使用 /trpg 启动"

        kp_id = session.get_kp_id()
        if not kp_id:
            return "❌ 当前团没有设置 KP，请联系管理员"

        try:
            # 投骰
            dice = DiceEngine()
            result = dice.roll(expression)

            # 群内显示（隐藏结果）
            group_msg = f"🎲 用户 {user_id} 进行暗骰：{reason}"

            # 私聊 KP（显示结果）
            kp_msg = f"""🔒 **暗骰结果**

玩家：{user_id}
原因：{reason}
结果：{result.detail} = **{result.total}**"""

            # 发送消息到群
            if context.onebot_client:
                await context.onebot_client.send_group_message(group_id, group_msg)

            # 发送私聊给 KP
            if context.onebot_client:
                await context.onebot_client.send_private_message(kp_id, kp_msg)

            return group_msg  # 返回群内消息

        except Exception as e:
            return f"❌ 暗骰失败：{str(e)}"
