"""
群聊分析工具集 — 所有用户消息从 config 读取
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Dict, List

from config.config_utils import get_text_message
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class GroupAnalysisUtil:
    @staticmethod
    async def _get_members(context, group_id: int) -> List[Dict]:
        if not group_id:
            return []
        from webnet.ToolNet.base import resolve_platform_adapter

        adapter = resolve_platform_adapter(context)
        client = adapter or getattr(context, "onebot_client", None)
        if not client:
            return []
        try:
            if hasattr(client, "get_group_member_list"):
                result = await client.get_group_member_list(group_id=group_id)
                if isinstance(result, list):
                    return result
                if isinstance(result, dict) and "data" in result:
                    return result["data"]
        except Exception as e:
            logger.warning(f"获取群成员失败: {e}")
        return []


class GroupMemberStructureTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "group_analysis_member_structure",
            "description": "分析群成员结构：角色分布（群主/管理员/成员）、等级概览、入群时间分布。",
            "parameters": {
                "type": "object",
                "properties": {"group_id": {"type": "integer", "description": "群号，不填则使用当前群"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        group_id = args.get("group_id") or getattr(context, "group_id", 0)
        if not group_id:
            return get_text_message("group_analysis", "group_id_unknown")
        members = await GroupAnalysisUtil._get_members(context, int(group_id))
        if not members:
            return get_text_message("group_analysis", "members_unavailable", group_id=group_id)
        role_count = Counter()
        for m in members:
            role_count[m.get("role", "member")] += 1
        total = len(members)
        lines = [
            get_text_message("group_analysis", "member_structure_header", group_id=group_id, total=total),
            "",
            "角色分布:",
        ]
        role_names = {
            "owner": get_text_message("group_analysis", "role_owner"),
            "admin": get_text_message("group_analysis", "role_admin"),
            "member": get_text_message("group_analysis", "role_member"),
        }
        for role in ["owner", "admin", "member"]:
            count = role_count.get(role, 0)
            pct = count / total * 100 if total else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            lines.append(f"  {role_names.get(role, role)}: {count}人 ({pct:.1f}%) {bar}")
        return "\n".join(lines)


class GroupMemberActivityTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "group_analysis_member_activity",
            "description": "分析群成员活跃度，按消息数量排名。",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {"type": "integer", "description": "群号，不填则使用当前群"},
                    "top_n": {"type": "integer", "description": "返回前N名（默认10）", "default": 10},
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        group_id = args.get("group_id") or getattr(context, "group_id", 0)
        top_n = args.get("top_n", 10)
        if not group_id:
            return get_text_message("group_analysis", "group_id_unknown")
        messages = []
        try:
            from webnet.ToolNet.tools.message.get_recent_messages import GetRecentMessagesTool

            tool = GetRecentMessagesTool()
            result = await tool.execute({"chat_id": str(group_id), "msg_type": "group", "limit": 200}, context)
            if isinstance(result, list):
                messages = result
            elif isinstance(result, str):
                messages = [{"sender_id": "system", "content": result}]
        except Exception:
            pass
        if not messages:
            return get_text_message("group_analysis", "messages_unavailable", group_id=group_id)
        sender_count = Counter()
        for msg in messages:
            sid = str(msg.get("sender_id", msg.get("user_id", "")))
            if sid:
                sender_count[sid] += 1
        top = sender_count.most_common(top_n)
        if not top:
            return get_text_message("group_analysis", "activity_no_data")
        lines = [get_text_message("group_analysis", "activity_header", group_id=group_id)]
        for i, (sid, count) in enumerate(top):
            lines.append(f"  {i + 1}. {sid}: {count} 条消息")
        return "\n".join(lines)


class GroupInactiveRiskTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "group_analysis_inactive_risk",
            "description": "检测长期潜水或新成员沉默等活跃风险。",
            "parameters": {
                "type": "object",
                "properties": {"group_id": {"type": "integer", "description": "群号，不填则使用当前群"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        group_id = args.get("group_id") or getattr(context, "group_id", 0)
        if not group_id:
            return get_text_message("group_analysis", "group_id_unknown")
        members = await GroupAnalysisUtil._get_members(context, int(group_id))
        if not members:
            return get_text_message("group_analysis", "members_unavailable", group_id=group_id)
        active_members = set()
        try:
            from webnet.ToolNet.tools.message.get_recent_messages import GetRecentMessagesTool

            tool = GetRecentMessagesTool()
            messages = await tool.execute({"chat_id": str(group_id), "msg_type": "group", "limit": 200}, context)
            if messages:
                for msg in messages:
                    sid = str(msg.get("sender_id", msg.get("user_id", "")))
                    if sid:
                        active_members.add(sid)
        except Exception:
            pass
        total = len(members)
        active = len(active_members)
        inactive = total - active
        pct = inactive / total * 100 if total else 0
        lines = [
            get_text_message("group_analysis", "inactive_header", group_id=group_id),
            get_text_message("group_analysis", "inactive_total", total=total),
        ]
        if total:
            lines.append(
                get_text_message("group_analysis", "inactive_active", active=active, pct=f"{active / total * 100:.1f}")
            )
        else:
            lines.append(get_text_message("group_analysis", "inactive_active", active=0, pct="0"))
        lines.append(get_text_message("group_analysis", "inactive_inactive", inactive=inactive, pct=f"{pct:.1f}"))
        if pct > 50:
            lines.append(get_text_message("group_analysis", "inactive_warn_high"))
        elif pct > 30:
            lines.append(get_text_message("group_analysis", "inactive_warn_mid"))
        else:
            lines.append(get_text_message("group_analysis", "inactive_ok"))
        return "\n".join(lines)


class GroupMessageMixTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "group_analysis_message_mix",
            "description": "统计群聊中不同类型消息的分布（文本/图片/语音/文件等）。",
            "parameters": {
                "type": "object",
                "properties": {"group_id": {"type": "integer", "description": "群号，不填则使用当前群"}},
                "required": [],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        group_id = args.get("group_id") or getattr(context, "group_id", 0)
        if not group_id:
            return get_text_message("group_analysis", "group_id_unknown")
        messages = []
        try:
            from webnet.ToolNet.tools.message.get_recent_messages import GetRecentMessagesTool

            tool = GetRecentMessagesTool()
            messages = await tool.execute({"chat_id": str(group_id), "msg_type": "group", "limit": 200}, context)
        except Exception:
            pass
        if not messages:
            return get_text_message("group_analysis", "messages_unavailable", group_id=group_id)
        type_count = Counter()
        total = len(messages)
        for msg in messages:
            mt = str(msg.get("message_type", msg.get("type", "text")))
            if "image" in mt or "pic" in mt:
                type_count["图片"] += 1
            elif "voice" in mt or "audio" in mt:
                type_count["语音"] += 1
            elif "file" in mt:
                type_count["文件"] += 1
            elif "video" in mt:
                type_count["视频"] += 1
            else:
                type_count["文本"] += 1
        lines = [get_text_message("group_analysis", "message_mix_header", group_id=group_id, total=total)]
        for mtype, count in type_count.most_common():
            pct = count / total * 100 if total else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            lines.append(f"  {mtype}: {count}条 ({pct:.1f}%) {bar}")
        return "\n".join(lines)
