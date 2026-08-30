"""
按昵称查找群成员
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class FindMember(BaseTool):
    """FindMember"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "find_member",
            "description": "按昵称、备注或QQ号查找群成员，获取用户的QQ号。当用户提到某个名字（如'分析威廉'）但未提供QQ号时，先使用此工具查找该成员，获取QQ号后再调用其他工具（如show_pc查看角色卡）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词（用户昵称、群备注或QQ号）"
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "群号，不指定则使用当前群"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大数量，默认10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["keyword"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        keyword = args.get("keyword", "").strip()
        group_id = args.get("group_id", context.group_id)
        limit = args.get("limit", 10)

        if not keyword:
            return "❌ 搜索关键词不能为空"

        if not group_id:
            return "❌ 无法确定群号，请指定 group_id"

        try:
            # 获取群成员列表
            if context.onebot_client:
                member_list = await context.onebot_client.get_group_member_list(group_id)

                if not member_list:
                    return f"📭 群 {group_id} 无成员或获取失败"

                # 搜索匹配的成员
                matches = []
                keyword_lower = keyword.lower()

                for member in member_list:
                    # 检查QQ号
                    if str(member.get('user_id', '')) == keyword:
                        matches.append(member)
                        continue

                    # 检查昵称
                    nickname = member.get('nickname', '') or member.get('card', '')
                    if keyword_lower in nickname.lower():
                        matches.append(member)
                        continue

                    # 检查备注
                    remark = member.get('remark', '')
                    if remark and keyword_lower in remark.lower():
                        matches.append(member)
                        continue

                # 限制结果
                matches = matches[:limit]

                if not matches:
                    return f"🔍 未找到匹配 '{keyword}' 的成员"

                # 格式化输出
                result = f"🔍 成员搜索结果: '{keyword}'\n群号: {group_id}\n共 {len(matches)} 个匹配\n\n"
                for i, member in enumerate(matches, 1):
                    user_id = member.get('user_id', '未知')
                    nickname = member.get('nickname', '') or member.get('card', '未知')
                    card = member.get('card', nickname)
                    role = member.get('role', 'member')
                    role_map = {
                        'owner': '群主',
                        'admin': '管理员',
                        'member': '成员'
                    }
                    role_name = role_map.get(role, role)

                    result += f"{i}. **{nickname}** ({user_id})\n"
                    if card and card != nickname:
                        result += f"   群名片: {card}\n"
                    result += f"   身份: {role_name}\n\n"

                return result
            else:
                logger.warning("onebot_client 不可用，无法查找成员")
                return "⚠️ OneBot 客户端不可用，无法查找群成员"

        except Exception as e:
            logger.error(f"查找成员失败: {e}", exc_info=True)
            return f"❌ 查找成员失败: {str(e)}"
