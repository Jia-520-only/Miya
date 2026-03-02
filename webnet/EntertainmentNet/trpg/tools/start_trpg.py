"""
启动跑团模式工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any


class StartTRPG(BaseTool):
    """启动跑团模式"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "start_trpg",
            "description": "启动 TRPG 跑团模式",
            "parameters": {
                "type": "object",
                "properties": {
                    "rule_system": {
                        "type": "string",
                        "enum": ["coc7", "dnd5e"],
                        "description": "规则系统"
                    },
                    "session_name": {
                        "type": "string",
                        "description": "团名称"
                    }
                }
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        rule_system = args.get("rule_system", "coc7")
        session_name = args.get("session_name", "未命名团")

        from ..session import get_session_manager
        session_manager = get_session_manager()

        session = session_manager.get_or_create(context.group_id or context.user_id)
        session.rule_system = rule_system
        session.session_name = session_name
        session_manager.save()

        rule_names = {
            "coc7": "COC 7版",
            "dnd5e": "D&D 5E"
        }

        return f"""🎲 **跑团模式已启动**

**规则系统**：{rule_names.get(rule_system, rule_system)}
**团名称**：{session_name}

**可用指令**：
• /roll 3d6         - 投骰
• /sc 侦查 70        - 技能检定
• /rs 1d100 侦查     - 暗骰
• /pc create 名字    - 创建角色卡
• /pc show           - 查看角色卡
• /kp set_mode       - 设置 KP 模式

开始你的冒险吧！🗡️"""
