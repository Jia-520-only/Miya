"""
获取群成员详细信息工具
"""
from typing import Dict, Any
import logging
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class GetMemberInfo(BaseTool):
    """获取群成员详细信息工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "get_member_info",
            "description": "获取群成员的详细信息（昵称、头衔、加群时间等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "integer",
                        "description": "群号，不指定则使用当前群"
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "用户QQ号"
                    },
                    "no_cache": {
                        "type": "boolean",
                        "description": "是否强制刷新",
                        "default": False
                    }
                },
                "required": ["user_id"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """获取群成员信息"""
        group_id = args.get("group_id") or context.group_id
        user_id = args.get("user_id")
        no_cache = args.get("no_cache", False)

        if not user_id:
            return "用户QQ号不能为空"

        if not group_id:
            return "无法确定群号"

        if not context.onebot_client:
            return "OneBot客户端未初始化"

        try:
            # 调用OneBot API
            info = await context.onebot_client.get_group_member_info(
                group_id, user_id, no_cache=no_cache
            )

            # 格式化返回
            result = f"""群成员信息:
QQ号: {info.get('user_id')}
群昵称: {info.get('card', info.get('nickname', '无'))}
群头衔: {info.get('title', '无')}
性别: {info.get('sex', 'unknown')}
等级: {info.get('level')}
加群时间: {info.get('join_time', '未知')}
最后发言: {info.get('last_sent_time', '未知')}
特殊身份: {', '.join(info.get('role_info', []))}"""

            return result

        except Exception as e:
            logger.error(f"获取成员信息失败: {e}", exc_info=True)
            return f"获取成员信息失败: {str(e)}"
