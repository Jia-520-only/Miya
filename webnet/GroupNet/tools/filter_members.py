"""
多条件筛选群成员
"""
from typing import Dict, Any, List
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class FilterMembers(BaseTool):
    """FilterMembers"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "filter_members",
            "description": "多条件筛选群成员（按身份、昵称长度、特殊标识等）。当用户明确要求筛选群成员时必须调用此工具。重要：此工具执行实际筛选操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "integer",
                        "description": "群号，不指定则使用当前群"
                    },
                    "role": {
                        "type": "string",
                        "description": "筛选身份：owner(群主), admin(管理员), member(成员)",
                        "enum": ["owner", "admin", "member"]
                    },
                    "nickname_contains": {
                        "type": "string",
                        "description": "昵称包含的关键词"
                    },
                    "has_card": {
                        "type": "boolean",
                        "description": "是否设置了群名片"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大数量，默认20",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        group_id = args.get("group_id", context.group_id)
        role = args.get("role")
        nickname_contains = args.get("nickname_contains")
        has_card = args.get("has_card")
        limit = args.get("limit", 20)

        if not group_id:
            return "❌ 无法确定群号，请指定 group_id"

        # 检查是否至少有一个筛选条件
        if not any([role, nickname_contains, has_card is not None]):
            return "❌ 至少需要一个筛选条件（role, nickname_contains, has_card）"

        try:
            if context.onebot_client:
                member_list = await context.onebot_client.get_group_member_list(group_id)

                if not member_list:
                    return f"📭 群 {group_id} 无成员或获取失败"

                # 筛选成员
                filtered = []
                for member in member_list:
                    # 身份筛选
                    if role and member.get('role') != role:
                        continue

                    # 昵称筛选
                    if nickname_contains:
                        nickname = member.get('nickname', '') or member.get('card', '')
                        if nickname_contains.lower() not in nickname.lower():
                            continue

                    # 群名片筛选
                    if has_card is not None:
                        card = member.get('card', '')
                        if has_card and not card:
                            continue
                        if not has_card and card:
                            continue

                    filtered.append(member)

                # 限制结果
                filtered = filtered[:limit]

                if not filtered:
                    return f"🔍 未找到符合条件的成员"

                # 格式化输出
                result = f"🔍 筛选结果\n群号: {group_id}\n共 {len(filtered)} 个成员\n\n"
                result += "筛选条件:\n"
                if role:
                    result += f"  身份: {role}\n"
                if nickname_contains:
                    result += f"  昵称包含: {nickname_contains}\n"
                if has_card is not None:
                    result += f"  有群名片: {'是' if has_card else '否'}\n"
                result += "\n"

                for i, member in enumerate(filtered, 1):
                    user_id = member.get('user_id', '未知')
                    nickname = member.get('nickname', '') or member.get('card', '未知')
                    card = member.get('card', '')
                    role_type = member.get('role', 'member')
                    role_map = {'owner': '群主', 'admin': '管理员', 'member': '成员'}
                    role_name = role_map.get(role_type, role_type)

                    result += f"{i}. **{nickname}** ({user_id}) - {role_name}\n"
                    if card:
                        result += f"   群名片: {card}\n"
                    result += "\n"

                return result
            else:
                logger.warning("onebot_client 不可用，无法筛选成员")
                return "⚠️ OneBot 客户端不可用，无法筛选群成员"

        except Exception as e:
            logger.error(f"筛选成员失败: {e}", exc_info=True)
            return f"❌ 筛选成员失败: {str(e)}"
