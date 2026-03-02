"""
获取群成员列表工具
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class GetMemberList(BaseTool):
    """获取群成员列表工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "get_member_list",
            "description": "获取群成员列表，可按权限筛选",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "integer",
                        "description": "群号，不指定则使用当前群"
                    },
                    "count": {
                        "type": "integer",
                        "description": "返回数量限制",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 500
                    },
                    "role": {
                        "type": "string",
                        "description": "筛选角色：owner(群主), admin(管理员), member(普通成员), all(全部)",
                        "enum": ["owner", "admin", "member", "all"],
                        "default": "all"
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """获取群成员列表"""
        group_id = args.get("group_id") or context.group_id
        count = args.get("count", 50)
        role = args.get("role", "all")

        if not group_id:
            return "无法确定群号"

        if not context.onebot_client:
            return "OneBot客户端未初始化"

        try:
            # 调用OneBot API
            member_list = await context.onebot_client.get_group_member_list(group_id)

            # 角色过滤
            if role != "all":
                role_map = {"owner": 4, "admin": 2, "member": 1}
                target_role = role_map.get(role, 1)
                member_list = [m for m in member_list if m.get("role") == target_role]

            # 限制数量
            member_list = member_list[:count]

            # 格式化返回
            result = f"群成员列表（共{len(member_list)}人）:\n"
            for i, member in enumerate(member_list, 1):
                nickname = member.get("nickname", member.get("card", "未知"))
                qq = member.get("user_id", "N/A")
                result += f"{i}. {nickname} ({qq})\n"

            return result

        except Exception as e:
            logger.error(f"获取成员列表失败: {e}", exc_info=True)
            return f"获取成员列表失败: {str(e)}"
