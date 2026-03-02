"""
查看角色卡工具
"""

from webnet.tools.base import BaseTool, ToolContext
from typing import Dict, Any


class ShowPC(BaseTool):
    """查看角色卡工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "show_pc",
            "description": "查看 TRPG 角色卡",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "玩家QQ号（不填则查看自己的）"
                    }
                }
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        target_user_id = args.get("user_id") or context.user_id
        group_id = context.group_id

        from ..character import get_character_manager

        character_manager = get_character_manager()
        pc = character_manager.get(target_user_id)

        if not pc:
            return f"❌ 未找到该玩家的角色卡，请使用 /pc create 创建"

        return f"""📋 **角色卡信息**

{pc.format_summary(group_id)}

**跨群状态**：{'已开启' if pc.shared_across_groups else '已关闭'}
**允许的群**：{', '.join(map(str, pc.allowed_groups)) if pc.allowed_groups else '无'}

**创建时间**：{pc.created_at.strftime('%Y-%m-%d %H:%M')}
**更新时间**：{pc.updated_at.strftime('%Y-%m-%d %H:%M')}"""
