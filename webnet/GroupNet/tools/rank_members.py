"""
按活跃度排行群成员
"""
from typing import Dict, Any
import logging
from datetime import datetime, timedelta
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class RankMembers(BaseTool):
    """RankMembers"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "rank_members",
            "description": "按活跃度排行群成员（基于近期消息统计或群内级别）。当用户说'活跃度排行'、'成员排行'、'群排行榜'等时必须调用此工具。重要：此工具执行实际查询操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "integer",
                        "description": "群号，不指定则使用当前群"
                    },
                    "metric": {
                        "type": "string",
                        "description": "排序指标：level(群等级), title(群头衔), join_time(加群时间), message_count(消息数)",
                        "enum": ["level", "title", "join_time", "message_count"],
                        "default": "level"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大数量，默认15",
                        "default": 15,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        group_id = args.get("group_id", context.group_id)
        metric = args.get("metric", "level")
        limit = args.get("limit", 15)

        if not group_id:
            return "❌ 无法确定群号，请指定 group_id"

        try:
            if context.onebot_client:
                member_list = await context.onebot_client.get_group_member_list(group_id)

                if not member_list:
                    return f"📭 群 {group_id} 无成员或获取失败"

                # 根据指标排序
                if metric == "level":
                    # 按群等级排序（level字段）
                    member_list.sort(key=lambda m: m.get('level', 0), reverse=True)
                    metric_name = "群等级"
                elif metric == "title":
                    # 按群头衔长度排序（有头衔的在前）
                    member_list.sort(key=lambda m: len(m.get('title', '') or ''), reverse=True)
                    metric_name = "群头衔"
                elif metric == "join_time":
                    # 按加群时间排序（最早加入的在前）
                    member_list.sort(key=lambda m: m.get('join_time', 0))
                    metric_name = "加群时间"
                elif metric == "message_count":
                    # 按消息数排序（如果有的话）
                    member_list.sort(key=lambda m: m.get('sent_count', 0), reverse=True)
                    metric_name = "消息数"

                # 限制结果
                ranked = member_list[:limit]

                # 格式化输出
                result = f"🏆 群成员活跃度排行榜\n"
                result += f"群号: {group_id}\n"
                result += f"排序指标: {metric_name}\n"
                result += f"共 {len(ranked)} 名\n\n"

                for i, member in enumerate(ranked, 1):
                    user_id = member.get('user_id', '未知')
                    nickname = member.get('nickname', '') or member.get('card', '未知')
                    card = member.get('card', '')
                    role = member.get('role', 'member')
                    role_map = {'owner': '群主', 'admin': '管理员', 'member': '成员'}
                    role_name = role_map.get(role, role)

                    # 前三名添加奖牌
                    medal = "🥇 " if i == 1 else "🥈 " if i == 2 else "🥉 " if i == 3 else f"{i}. "

                    result += f"{medal}**{nickname}**\n"
                    result += f"   QQ: {user_id} | 身份: {role_name}\n"

                    # 根据指标显示不同信息
                    if metric == "level":
                        level = member.get('level', 0)
                        result += f"   群等级: {level}\n"
                    elif metric == "title":
                        title = member.get('title', '') or '无'
                        result += f"   群头衔: {title}\n"
                    elif metric == "join_time":
                        join_time = member.get('join_time', 0)
                        if join_time:
                            join_date = datetime.fromtimestamp(join_time).strftime('%Y-%m-%d')
                            days = (datetime.now() - datetime.fromtimestamp(join_time)).days
                            result += f"   加群时间: {join_date} ({days}天前)\n"
                    elif metric == "message_count":
                        msg_count = member.get('sent_count', 0)
                        result += f"   消息数: {msg_count}\n"

                    result += "\n"

                return result
            else:
                logger.warning("onebot_client 不可用，无法排行成员")
                return "⚠️ OneBot 客户端不可用，无法排行群成员"

        except Exception as e:
            logger.error(f"排行成员失败: {e}", exc_info=True)
            return f"❌ 排行成员失败: {str(e)}"
