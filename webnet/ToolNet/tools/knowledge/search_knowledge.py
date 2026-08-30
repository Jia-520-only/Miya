"""
搜索知识工具 — 从本地知识库检索知识
"""

import logging
from typing import Any, Dict

from config.config_utils import get_text_message
from webnet.ToolNet.base import BaseTool
from webnet.ToolNet.tools.knowledge.knowledge_store import get_knowledge_store

logger = logging.getLogger(__name__)


class SearchKnowledgeTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "search_knowledge",
            "description": "从弥娅的本地知识库搜索相关知识。当用户问'你知道xxx吗'、'查一下xxx'、'之前存过xxx'或需要查找已保存的知识时使用。支持语义搜索和关键词搜索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或语义描述"},
                    "category": {"type": "string", "description": "限定分类（可选）"},
                    "limit": {"type": "integer", "description": "返回结果数量限制（默认10，最大20）", "default": 10},
                    "method": {
                        "type": "string",
                        "description": "搜索方式：semantic（语义搜索，默认）、keyword（关键词搜索）",
                        "enum": ["semantic", "keyword"],
                        "default": "semantic",
                    },
                },
                "required": ["query"],
            },
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        query = args.get("query", "")
        category = args.get("category", "")
        limit = min(args.get("limit", 10), 20)
        method = args.get("method", "semantic")

        if not query.strip():
            return get_text_message("knowledge_base", "query_required")

        store = get_knowledge_store()
        if method == "semantic":
            results = await store.search_semantic(query, limit, category)
        else:
            results = await store.search_keyword(query, limit, category)

        if not results:
            stats = await store.get_stats()
            if stats["total_entries"] == 0:
                return get_text_message("knowledge_base", "empty_search")
            return get_text_message("knowledge_base", "no_results", query=query, total=stats["total_entries"])

        lines = [get_text_message("knowledge_base", "search_header", query=query, count=len(results))]
        for i, r in enumerate(results):
            content_preview = r["content"][:200]
            if len(r["content"]) > 200:
                content_preview += "..."
            score_info = f" (相关度: {r['score']})" if r.get("score") else ""
            lines.append(f"\n{i + 1}. [{r['category']}] {r['title']}{score_info}")
            lines.append(f"   {content_preview}")
            lines.append(f"   ID: `{r['id']}`")
        return "\n".join(lines)
