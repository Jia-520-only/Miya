"""
搜索认知事件工具 — 从 config 读取消息
"""

import logging
from typing import Any, Dict

from config.config_utils import get_text_message
from webnet.ToolNet.base import BaseTool
from webnet.ToolNet.tools.cognitive.profile_storage import get_profile_storage

logger = logging.getLogger(__name__)


class SearchEventsTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_events",
            "description": "搜索历史认知事件记忆，用于回忆之前发生过的事情。当对话中出现'之前'、'上次'、'你记得吗'、'继续'、'按我的习惯'等需要回溯历史时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或语义描述"},
                    "entity_type": {
                        "type": "string",
                        "description": "实体类型：user（用户）或 group（群聊）",
                        "enum": ["user", "group"],
                    },
                    "entity_id": {"type": "string", "description": "实体ID：用户QQ号或群号。不填则从上下文自动获取"},
                    "top_k": {"type": "integer", "description": "返回条数（默认10，最大20）", "default": 10},
                },
                "required": ["query"],
            },
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        query = args.get("query", "")
        entity_type = args.get("entity_type", "user")
        entity_id = str(args.get("entity_id", ""))
        top_k = min(args.get("top_k", 10), 20)
        if not query.strip():
            return get_text_message("cognitive_memory", "query_required")
        if not entity_id or entity_id == "0" or entity_id == "None":
            if entity_type == "user":
                entity_id = str(getattr(context, "user_id", ""))
            elif entity_type == "group":
                entity_id = str(getattr(context, "group_id", ""))
        if not entity_id or entity_id == "0" or entity_id == "None":
            type_label = "用户" if entity_type == "user" else "群聊"
            return get_text_message("cognitive_memory", "entity_unknown", type=type_label)

        storage = get_profile_storage()
        observations = await storage.get_observations(entity_type, entity_id, limit=100)
        profile = await storage.read_profile(entity_type, entity_id)

        query_lower = query.lower()
        matched = []
        for obs in observations:
            obs_text = obs.get("observation", "")
            if query_lower in obs_text.lower():
                matched.append(obs)
            else:
                for word in query_lower.split():
                    if word in obs_text.lower():
                        matched.append(obs)
                        break
        if not matched and profile:
            if query_lower in profile.lower():
                matched.append({"observation": f"侧写中包含相关信息: {query}", "source": "profile", "timestamp": ""})
        if not matched:
            return get_text_message("cognitive_memory", "events_no_results", query=query)
        matched = matched[:top_k]
        type_label = "用户" if entity_type == "user" else "群聊"
        lines = [
            get_text_message("cognitive_memory", "events_header", type=type_label, entity_id=entity_id, query=query)
        ]
        for i, obs in enumerate(matched):
            ts = obs.get("timestamp", "")[:19] if obs.get("timestamp") else ""
            lines.append(f"\n{i + 1}. {obs['observation']}")
            if ts:
                lines.append(f"   时间: {ts}")
        return "\n".join(lines)
