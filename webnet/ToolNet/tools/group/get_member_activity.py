"""
获取群成员活跃度工具
"""

import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class GetMemberActivityTool(BaseTool):
    """群成员活跃度分析工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "get_member_activity",
            "description": "分析群成员活跃度，支持多种模式：member_list(仅成员列表)、history(历史消息)、hybrid(融合模式)。可输出活跃统计、活跃榜和潜水成员。",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {"type": "integer", "description": "群号"},
                    "threshold_days": {
                        "type": "integer",
                        "description": "非活跃阈值(天数)，默认30天",
                        "default": 30,
                    },
                    "source": {
                        "type": "string",
                        "description": "数据源模式",
                        "enum": ["member_list", "history", "hybrid"],
                        "default": "hybrid",
                    },
                    "count": {
                        "type": "integer",
                        "description": "返回最活跃/最不活跃成员数量，默认10",
                        "default": 10,
                    },
                },
                "required": ["group_id"],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}

        group_id = args.get("group_id", context.group_id)
        if not group_id:
            return "请指定群号"

        threshold_days = args.get("threshold_days", 30)
        source = args.get("source", "hybrid")
        count = args.get("count", 10)

        return await self._analyze_activity(group_id, threshold_days, source, count, context)

    async def _analyze_activity(
        self, group_id: int, threshold_days: int, source: str, count: int, context: ToolContext
    ) -> str:
        """分析群成员活跃度"""
        try:
            from webnet.ToolNet.base import resolve_platform_adapter

            client = resolve_platform_adapter(context) or getattr(context, "onebot_client", None)
            if not client:
                return "当前平台不支持群成员查询"

            if source in ["member_list", "hybrid"]:
                members = await client.get_group_member_list(group_id)

                if not members:
                    return f"群 {group_id} 成员列表获取失败"

                # 按最后发言时间排序
                active_members = []
                for m in members:
                    last_sent = m.get("last_sent_time", 0)
                    import time

                    if last_sent:
                        days_ago = (time.time() - last_sent) / 86400
                        active_members.append((m, days_ago))

                active_members.sort(key=lambda x: x[1])

                active_list = active_members[:count]
                inactive_list = active_members[-count:][::-1] if len(active_members) > count else []

                lines = [f"【群 {group_id} 活跃度分析】\n"]
                lines.append(f"总成员: {len(members)} | 阈值: {threshold_days}天\n")

                lines.append(f"\n【最活跃的 {count} 位】")
                for i, (m, days) in enumerate(active_list):
                    name = m.get("nickname", m.get("card", f"QQ{m.get('user_id')}"))
                    if days < 1:
                        lines.append(f"{i + 1}. {name} - 今日活跃")
                    elif days < 7:
                        lines.append(f"{i + 1}. {name} - {int(days)}天内活跃")
                    else:
                        lines.append(f"{i + 1}. {name} - {int(days)}天前活跃")

                if inactive_list:
                    lines.append(f"\n【潜水的 {count} 位】")
                    for i, (m, days) in enumerate(inactive_list):
                        name = m.get("nickname", m.get("card", f"QQ{m.get('user_id')}"))
                        lines.append(f"{i + 1}. {name} - {int(days)}天无发言")

                return "\n".join(lines)

            return "历史消息分析功能暂未实现"

        except Exception as e:
            logger.error(f"获取群成员活跃度失败: {e}")
            return f"获取活跃度失败: {str(e)[:50]}"


def get_member_activity_tool():
    return GetMemberActivityTool()
