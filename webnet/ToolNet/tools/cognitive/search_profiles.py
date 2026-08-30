"""
搜索认知侧写工具 — 从 config 读取所有消息
"""

import logging
from typing import Any, Dict

from config.config_utils import get_text_message
from webnet.ToolNet.base import BaseTool
from webnet.ToolNet.tools.cognitive.profile_storage import get_profile_storage

logger = logging.getLogger(__name__)


class SearchProfilesTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_profiles",
            "description": "搜索具有特定特征的用户或群聊侧写。例如：查找'喜欢编程'的用户、查找'活跃的游戏群'等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或特征描述"},
                    "entity_type": {
                        "type": "string",
                        "description": "限定类型：user（用户）或 group（群聊），不填则搜索全部",
                        "enum": ["user", "group"],
                    },
                    "top_k": {"type": "integer", "description": "返回条数（默认8，最大20）", "default": 8},
                },
                "required": ["query"],
            },
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        query = args.get("query", "")
        entity_type = args.get("entity_type", "")
        top_k = min(args.get("top_k", 8), 20)
        if not query.strip():
            return get_text_message("cognitive_memory", "query_required")
        storage = get_profile_storage()
        results = await storage.search_profiles(query, entity_type, top_k)
        if not results:
            return get_text_message("cognitive_memory", "search_no_results", query=query)
        lines = [get_text_message("cognitive_memory", "search_header", query=query, count=len(results))]
        for i, r in enumerate(results):
            type_label = "用户" if r["entity_type"] == "user" else "群聊"
            lines.append(f"\n{i + 1}. [{type_label}] ID: {r['entity_id']} (相关度: {r['score']})")
            lines.append(f"   {r['content'][:200]}...")
        return "\n".join(lines)
