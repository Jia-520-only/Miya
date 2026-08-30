"""
删除知识工具 — 从本地知识库删除知识条目
"""

import logging
from typing import Any, Dict

from config.config_utils import get_text_message
from webnet.ToolNet.base import BaseTool
from webnet.ToolNet.tools.knowledge.knowledge_store import get_knowledge_store

logger = logging.getLogger(__name__)


class DeleteKnowledgeTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "delete_knowledge",
            "description": "从弥娅的本地知识库中删除指定的知识条目。当用户要求删除某条知识、或者知识已过时时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "knowledge_id": {"type": "string", "description": "知识ID（从 search_knowledge 结果中获取）"},
                    "title": {"type": "string", "description": "知识标题（用于匹配，与 knowledge_id 任选其一）"},
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        knowledge_id = args.get("knowledge_id", "")
        title = args.get("title", "")
        store = get_knowledge_store()

        if knowledge_id:
            success = await store.delete(knowledge_id)
            if success:
                return get_text_message("knowledge_base", "deleted", knowledge_id=knowledge_id)
            return get_text_message("knowledge_base", "not_found", knowledge_id=knowledge_id)

        if title:
            results = await store.search_keyword(title, limit=5)
            if not results:
                return get_text_message("knowledge_base", "no_results", query=title, total=0)
            if len(results) == 1:
                r = results[0]
                await store.delete(r["id"])
                return get_text_message("knowledge_base", "deleted", knowledge_id=r["id"])
            lines = [get_text_message("knowledge_base", "multi_match", count=len(results), title=title)]
            for r in results:
                lines.append(f"- `{r['id']}`: {r['title']}")
            return "\n".join(lines)

        return get_text_message("knowledge_base", "id_or_title_required")
